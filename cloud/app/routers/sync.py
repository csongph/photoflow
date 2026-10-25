from __future__ import annotations

import hashlib
import hmac
import os
import re

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Event, FaceSearchSession, GallerySettings, Photo, PhotoFace, PhotoVariant, SyncJob

router = APIRouter(prefix="/api/sync", tags=["sync"])


def event_out(event: Event, settings: GallerySettings | None) -> dict:
    return {
        "public_id": event.public_id,
        "name": event.name,
        "event_date": event.event_date,
        "description": event.description,
        "pin_hash": event.pin_hash,
        "gallery_settings": {
            "pin_hash": event.pin_hash,
            "enable_gallery": settings.enabled if settings else True,
            "allow_download": settings.allow_download if settings else True,
            "auto_refresh": settings.auto_refresh if settings else True,
            "credit_text": settings.credit_text if settings else "",
            "report_contact": settings.report_contact if settings else "",
        },
        "photos": [
            {
                "local_photo_id": photo.local_photo_id,
                "filename": photo.filename,
                "capture_id": photo.capture_id,
                "storage_provider": photo.storage_provider,
                "storage_object_id": photo.storage_object_id,
                "published": photo.published,
                "hidden": photo.hidden,
                "variants": [
                    {"kind": row.kind, "storage_provider": row.storage_provider, "storage_object_id": row.storage_object_id, "width": row.width, "height": row.height}
                    for row in photo.variants
                ],
            }
            for photo in event.photos
        ],
    }


def pin_hash(value: str) -> str:
    value = value.strip()
    return hashlib.sha256(value.encode("utf-8")).hexdigest() if value else ""


def public_id_from(payload: dict) -> str:
    public_id = str(payload.get("public_id") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", public_id):
        raise HTTPException(422, "Invalid public_id")
    return public_id


def require_sync_token(authorization: str = Header("")) -> None:
    expected = os.getenv("CLOUD_SYNC_TOKEN", "").strip()
    if not expected:
        raise HTTPException(503, "Cloud sync token is not configured")
    if not hmac.compare_digest(authorization, f"Bearer {expected}"):
        raise HTTPException(401, "Invalid sync token")


@router.post("/event")
def sync_event(payload: dict, db: Session = Depends(get_db), _: None = Depends(require_sync_token)):
    public_id = public_id_from(payload)
    name = str(payload.get("name") or "").strip()
    if not name or len(name) > 180:
        raise HTTPException(422, "Invalid event name")
    event = db.query(Event).filter(Event.public_id == public_id).first() or Event(public_id=public_id)
    event.name = name
    event_date = str(payload.get("event_date") or "").strip()
    description = str(payload.get("description") or "").strip()
    if len(event_date) > 20 or len(description) > 10000:
        raise HTTPException(422, "Invalid event metadata")
    event.event_date = event_date
    event.description = description
    incoming_settings = payload.get("gallery_settings")
    incoming_settings = incoming_settings if isinstance(incoming_settings, dict) else {}
    incoming_pin_hash = str(incoming_settings.get("pin_hash") or "").strip()
    if incoming_pin_hash and (len(incoming_pin_hash) != 64 or any(ch not in "0123456789abcdef" for ch in incoming_pin_hash.lower())):
        raise HTTPException(422, "Invalid gallery PIN hash")
    event.pin_hash = incoming_pin_hash if incoming_pin_hash else ""
    db.add(event)
    db.flush()
    allowed = {"allow_download", "auto_refresh", "credit_text", "report_contact"}
    gallery_settings = {k: v for k, v in incoming_settings.items() if k in allowed}
    enabled = incoming_settings.get("enable_gallery", True)
    if not isinstance(enabled, bool):
        raise HTTPException(422, "Invalid gallery setting: enable_gallery")
    gallery_settings["enabled"] = enabled
    gallery_settings["find_my_photos"] = False
    for key in ("allow_download", "auto_refresh"):
        if key in incoming_settings:
            if not isinstance(incoming_settings[key], bool):
                raise HTTPException(422, f"Invalid gallery setting: {key}")
            gallery_settings[key] = incoming_settings[key]
    for key, limit in (("credit_text", 220), ("report_contact", 220)):
        value = incoming_settings.get(key, "")
        if not isinstance(value, str) or len(value) > limit:
            raise HTTPException(422, f"Invalid gallery setting: {key}")
    db.merge(GallerySettings(event_id=event.id, **gallery_settings))
    db.commit()
    return {"event_id": event.id, "public_id": event.public_id}


@router.get("/events")
def list_cloud_events(db: Session = Depends(get_db), _: None = Depends(require_sync_token)):
    events = db.query(Event).order_by(Event.updated_at.desc()).all()
    result = []
    for event in events:
        result.append(event_out(event, db.get(GallerySettings, event.id)))
    return result


@router.post("/photo")
def sync_photo(payload: dict, db: Session = Depends(get_db), _: None = Depends(require_sync_token)):
    public_id = public_id_from(payload)
    local_photo_id = str(payload.get("local_photo_id") or "").strip()
    if not local_photo_id or len(local_photo_id) > 64:
        raise HTTPException(422, "Invalid local_photo_id")
    event = db.query(Event).filter(Event.public_id == public_id).first()
    if not event:
        raise HTTPException(409, "Event must be synced before its photos")
    photo = db.query(Photo).filter(Photo.event_id == event.id, Photo.local_photo_id == local_photo_id).first()
    if not photo:
        photo = Photo(event_id=event.id, local_photo_id=local_photo_id)
    filename = str(payload.get("filename") or getattr(photo, "filename", "") or f"{local_photo_id}.jpg").strip()
    capture_id = str(payload.get("capture_id") or getattr(photo, "capture_id", "") or local_photo_id).strip()
    storage_provider = str(payload.get("storage_provider") or getattr(photo, "storage_provider", "") or "local").strip()
    storage_object_id = str(payload.get("storage_object_id") or getattr(photo, "storage_object_id", "") or "").strip()
    if not filename or len(filename) > 260 or not capture_id or len(capture_id) > 220 or len(storage_provider) > 60 or len(storage_object_id) > 300:
        raise HTTPException(422, "Invalid photo metadata")
    photo.filename = filename
    photo.capture_id = capture_id
    photo.storage_provider = storage_provider
    photo.storage_object_id = storage_object_id
    for key in ("published", "hidden"):
        if key in payload and not isinstance(payload[key], bool):
            raise HTTPException(422, f"Invalid photo field: {key}")
    photo.published = payload.get("published", getattr(photo, "published", False))
    photo.hidden = payload.get("hidden", getattr(photo, "hidden", False))
    db.add(photo)
    db.flush()
    variants = payload.get("variants") if isinstance(payload.get("variants"), list) else []
    if len(variants) > 5:
        raise HTTPException(422, "Too many photo variants")
    seen_kinds: set[str] = set()
    for variant in variants:
        if not isinstance(variant, dict):
            continue
        kind = str(variant.get("kind") or "finished").strip()
        provider = str(variant.get("storage_provider") or storage_provider).strip()
        object_id = str(variant.get("storage_object_id") or "").strip()
        if kind not in {"finished", "preview", "thumbnail"} or kind in seen_kinds or not object_id or len(provider) > 60 or len(object_id) > 300:
            raise HTTPException(422, "Invalid photo variant")
        seen_kinds.add(kind)
        row = db.query(PhotoVariant).filter(PhotoVariant.photo_id == photo.id, PhotoVariant.kind == kind).first()
        if not row:
            row = PhotoVariant(photo_id=photo.id, kind=kind)
        for key in ["storage_provider", "storage_object_id", "width", "height"]:
            setattr(row, key, variant.get(key, getattr(row, key, None)))
        try:
            width = max(0, int(variant.get("width") or 0))
            height = max(0, int(variant.get("height") or 0))
        except (TypeError, ValueError):
            raise HTTPException(422, "Invalid photo variant dimensions")
        if width > 100000 or height > 100000:
            raise HTTPException(422, "Invalid photo variant dimensions")
        row.storage_provider = provider
        row.storage_object_id = object_id
        row.width = width
        row.height = height
        db.add(row)
    db.commit()
    return {"photo_id": photo.id}


@router.delete("/event/{public_id}")
def delete_event(public_id: str, db: Session = Depends(get_db), _: None = Depends(require_sync_token)):
    event = db.query(Event).filter(Event.public_id == public_id).first()
    if not event:
        return {"ok": True, "deleted": False}
    # Child rows use ON DELETE CASCADE; deleting the parent lets PostgreSQL
    # remove all associated gallery and face metadata atomically.
    photo_ids = [row[0] for row in db.query(Photo.id).filter(Photo.event_id == event.id).all()]
    if photo_ids:
        db.query(PhotoVariant).filter(PhotoVariant.photo_id.in_(photo_ids)).delete(synchronize_session=False)
    db.query(PhotoFace).filter(PhotoFace.event_id == event.id).delete(synchronize_session=False)
    db.query(FaceSearchSession).filter(FaceSearchSession.event_id == event.id).delete(synchronize_session=False)
    db.query(SyncJob).filter(SyncJob.event_id == event.id).delete(synchronize_session=False)
    db.query(Photo).filter(Photo.event_id == event.id).delete(synchronize_session=False)
    db.query(GallerySettings).filter(GallerySettings.event_id == event.id).delete(synchronize_session=False)
    db.delete(event)
    db.commit()
    return {"ok": True, "deleted": True}
