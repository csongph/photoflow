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
    event.event_date = payload.get("event_date", "")
    event.description = payload.get("description", "")
    event.pin_hash = pin_hash(str(payload.get("gallery_settings", {}).get("optional_pin") or ""))
    db.add(event)
    db.flush()
    allowed = {"allow_download", "auto_refresh", "credit_text", "report_contact"}
    gallery_settings = {k: v for k, v in payload.get("gallery_settings", {}).items() if k in allowed}
    gallery_settings["enabled"] = bool(payload.get("gallery_settings", {}).get("enable_gallery", True))
    gallery_settings["find_my_photos"] = False
    db.merge(GallerySettings(event_id=event.id, **gallery_settings))
    db.commit()
    return {"event_id": event.id, "public_id": event.public_id}


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
    for key in ["filename", "capture_id", "storage_provider", "storage_object_id", "published", "hidden"]:
        setattr(photo, key, payload.get(key, getattr(photo, key, None)))
    db.add(photo)
    db.flush()
    for variant in payload.get("variants", []):
        row = db.query(PhotoVariant).filter(PhotoVariant.photo_id == photo.id, PhotoVariant.kind == variant.get("kind")).first()
        if not row:
            row = PhotoVariant(photo_id=photo.id, kind=variant.get("kind", "finished"))
        for key in ["storage_provider", "storage_object_id", "width", "height"]:
            setattr(row, key, variant.get(key, getattr(row, key, None)))
        db.add(row)
    db.commit()
    return {"photo_id": photo.id}


@router.delete("/event/{public_id}")
def delete_event(public_id: str, db: Session = Depends(get_db), _: None = Depends(require_sync_token)):
    event = db.query(Event).filter(Event.public_id == public_id).first()
    if not event:
        return {"ok": True, "deleted": False}
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
