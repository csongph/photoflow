from __future__ import annotations

import hashlib
import hmac
import json
import os
import re

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from PIL import Image
from io import BytesIO
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CardTemplate, Event, FaceSearchSession, GallerySettings, Photo, PhotoFace, PhotoStripAsset, PhotoVariant, SyncJob

router = APIRouter(prefix="/api/sync", tags=["sync"])


def event_out(event: Event, settings: GallerySettings | None, *, include_photos: bool = False) -> dict:
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
            "card_maker_enabled": bool(settings.card_maker_enabled and settings.card_template_name) if settings else False,
            "card_template_name": settings.card_template_name if settings else "",
            "photo_strip_enabled": bool(settings.photo_strip_enabled) if settings else False,
            "photo_strip": _photo_strip_config(settings.photo_strip_config_json if settings else "{}"),
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
        ] if include_photos else [],
    }


def pin_hash(value: str) -> str:
    value = value.strip()
    return hashlib.sha256(value.encode("utf-8")).hexdigest() if value else ""


def _photo_strip_config(raw: str | None) -> dict:
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}


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


def _upsert_sync_row(db: Session, model, values: dict, conflict_columns: list) -> None:
    """Atomically insert/update sync rows across worker requests."""
    dialect = db.get_bind().dialect.name
    insert_fn = pg_insert if dialect == "postgresql" else sqlite_insert if dialect == "sqlite" else None
    if insert_fn is None:
        raise RuntimeError(f"Unsupported sync database dialect: {dialect}")
    statement = insert_fn(model).values(**values)
    conflict_names = {column.key for column in conflict_columns}
    updates = {
        key: getattr(statement.excluded, key)
        for key in values
        if key not in conflict_names
    }
    db.execute(statement.on_conflict_do_update(index_elements=conflict_columns, set_=updates))


@router.post("/event")
def sync_event(payload: dict, db: Session = Depends(get_db), _: None = Depends(require_sync_token)):
    public_id = public_id_from(payload)
    name = str(payload.get("name") or "").strip()
    if not name or len(name) > 180:
        raise HTTPException(422, "Invalid event name")
    event_date = str(payload.get("event_date") or "").strip()
    description = str(payload.get("description") or "").strip()
    if len(event_date) > 20 or len(description) > 10000:
        raise HTTPException(422, "Invalid event metadata")
    incoming_settings = payload.get("gallery_settings")
    incoming_settings = incoming_settings if isinstance(incoming_settings, dict) else {}
    incoming_pin_hash = str(incoming_settings.get("pin_hash") or "").strip()
    if incoming_pin_hash and (len(incoming_pin_hash) != 64 or any(ch not in "0123456789abcdef" for ch in incoming_pin_hash.lower())):
        raise HTTPException(422, "Invalid gallery PIN hash")
    allowed = {"allow_download", "auto_refresh", "credit_text", "report_contact", "card_maker_enabled", "card_template_name", "photo_strip_enabled", "photo_strip_config_json"}
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
    if "card_maker_enabled" in incoming_settings and not isinstance(incoming_settings["card_maker_enabled"], bool):
        raise HTTPException(422, "Invalid gallery setting: card_maker_enabled")
    if "photo_strip_enabled" in incoming_settings and not isinstance(incoming_settings["photo_strip_enabled"], bool):
        raise HTTPException(422, "Invalid gallery setting: photo_strip_enabled")
    strip_config_json = incoming_settings.get("photo_strip_config_json", "{}")
    if not isinstance(strip_config_json, str) or len(strip_config_json) > 250_000:
        raise HTTPException(422, "Invalid Photo Strip configuration")
    strip_config = _photo_strip_config(strip_config_json)
    if not isinstance(strip_config.get("themes", []), list) or len(strip_config.get("themes", [])) > 20:
        raise HTTPException(422, "Invalid Photo Strip theme list")
    template_name = incoming_settings.get("card_template_name", "")
    if not isinstance(template_name, str) or len(template_name) > 160:
        raise HTTPException(422, "Invalid gallery setting: card_template_name")
    for key, limit in (
        ("credit_text", 220),
        ("report_contact", 220),
    ):
        value = incoming_settings.get(key, "")
        if not isinstance(value, str) or len(value) > limit:
            raise HTTPException(422, f"Invalid gallery setting: {key}")
    event_values = {
        "public_id": public_id,
        "name": name,
        "event_date": event_date,
        "description": description,
        "pin_hash": incoming_pin_hash if incoming_pin_hash else "",
    }
    _upsert_sync_row(db, Event, event_values, [Event.public_id])
    event = db.query(Event).filter(Event.public_id == public_id).first()
    if event is None:
        raise RuntimeError("Cloud event upsert completed without a readable event")

    settings_values = {"event_id": event.id, **gallery_settings}
    if "photo_strip_enabled" in incoming_settings:
        settings_values["photo_strip_enabled"] = incoming_settings["photo_strip_enabled"]
    if "photo_strip_config_json" in incoming_settings:
        settings_values["photo_strip_config_json"] = strip_config_json
    elif "photo_strip_enabled" in incoming_settings:
        settings_values["photo_strip_config_json"] = "{}"
    _upsert_sync_row(db, GallerySettings, settings_values, [GallerySettings.event_id])
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"event_id": event.id, "public_id": event.public_id}


@router.post("/events/{public_id}/photo-strip-asset")
async def sync_photo_strip_asset(public_id: str, theme_id: str = Form(...), photo_count: int = Form(...), template: UploadFile = File(...), db: Session = Depends(get_db), _: None = Depends(require_sync_token)):
    event = db.query(Event).filter(Event.public_id == public_id).first()
    if not event:
        raise HTTPException(404, "Event not found")
    if photo_count not in (2, 3, 4) or len(theme_id) > 64 or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for ch in theme_id):
        raise HTTPException(422, "Invalid Photo Strip layout key")
    config = _photo_strip_config((db.get(GallerySettings, event.id) or GallerySettings(event_id=event.id)).photo_strip_config_json)
    theme = next((item for item in config.get("themes", []) if isinstance(item, dict) and item.get("id") == theme_id), None)
    layout = theme.get("layouts", {}).get(str(photo_count), {}) if theme else {}
    slots = layout.get("slots") if isinstance(layout, dict) else None
    if not isinstance(slots, list) or len(slots) != photo_count:
        raise HTTPException(422, "Photo Strip layout does not match the configured slot count")
    filename = (template.filename or "").replace("\\", "/").split("/")[-1][:160]
    if not filename.lower().endswith(".png"):
        raise HTTPException(415, "Photo Strip layout must be PNG")
    content = await template.read(8 * 1024 * 1024 + 1)
    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(413, "Photo Strip layout exceeds 8 MB")
    try:
        with Image.open(BytesIO(content)) as image:
            if image.format != "PNG" or min(image.size) < 300 or max(image.size) > 5000 or image.width >= image.height:
                raise HTTPException(422, "Photo Strip template must be a portrait PNG between 300 and 5000 px")
            image.load()
            alpha = image.convert("RGBA").resize((100, 100)).getchannel("A")
            for slot in slots:
                x0, x1 = round((slot["x"] + slot["width"] * .35) * 100), round((slot["x"] + slot["width"] * .65) * 100)
                y0, y1 = round((slot["y"] + slot["height"] * .35) * 100), round((slot["y"] + slot["height"] * .65) * 100)
                sample = alpha.crop((x0, y0, x1, y1))
                if not sample.width or not sample.height or sum(value < 40 for value in sample.getdata()) < sample.width * sample.height * .6:
                    raise HTTPException(422, "Photo Strip PNG must contain transparent photo areas at configured slot positions")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, "Invalid Photo Strip PNG") from exc
    row = db.query(PhotoStripAsset).filter_by(event_id=event.id, theme_id=theme_id, photo_count=photo_count).first()
    if row is None:
        row = PhotoStripAsset(event_id=event.id, theme_id=theme_id, photo_count=photo_count)
    row.image_data = content
    db.add(row)
    db.commit()
    return {"ok": True, "theme_id": theme_id, "photo_count": photo_count, "filename": filename}


@router.delete("/events/{public_id}/photo-strip-asset")
def delete_photo_strip_asset(public_id: str, theme_id: str, photo_count: int, db: Session = Depends(get_db), _: None = Depends(require_sync_token)):
    event = db.query(Event).filter(Event.public_id == public_id).first()
    if not event:
        raise HTTPException(404, "Event not found")
    if photo_count not in (2, 3, 4):
        raise HTTPException(422, "Invalid Photo Strip layout")
    row = db.query(PhotoStripAsset).filter_by(event_id=event.id, theme_id=theme_id, photo_count=photo_count).first()
    if row:
        db.delete(row)
        db.commit()
    return {"ok": True}


@router.post("/events/{public_id}/card-template")
async def sync_card_template(public_id: str, template: UploadFile = File(...), enabled: bool = Form(True), db: Session = Depends(get_db), _: None = Depends(require_sync_token)):
    event = db.query(Event).filter(Event.public_id == public_id).first()
    if not event:
        raise HTTPException(404, "Event not found")
    filename = (template.filename or "").replace("\\", "/").split("/")[-1][:160]
    if not filename.lower().endswith(".png"):
        raise HTTPException(415, "Card template must be PNG")
    content = await template.read(8 * 1024 * 1024 + 1)
    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(413, "Card template exceeds 8 MB")
    try:
        with Image.open(BytesIO(content)) as image:
            if image.format != "PNG":
                raise HTTPException(415, "Card template must be PNG")
            if min(image.size) < 300 or max(image.size) > 5000 or image.width >= image.height:
                raise HTTPException(422, "Card template must be portrait, 300–5000 px, and taller than wide")
            image.load()
            rgba = image.convert("RGBA")
            if min(rgba.getchannel("A").getextrema()) == 255:
                raise HTTPException(422, "Card template must contain transparent photo areas")
            alpha = rgba.resize((100, 100)).getchannel("A")
            for cy in (.2425,.4325,.6225,.8125):
                sample = alpha.crop((35, round((cy-.05)*100), 65, round((cy+.05)*100)))
                if sum(value < 40 for value in sample.getdata()) < sample.width * sample.height * .6:
                    raise HTTPException(422, "Template must leave four transparent photo slots in a vertical strip")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, "Invalid card template PNG") from exc
    settings = db.get(GallerySettings, event.id) or GallerySettings(event_id=event.id)
    settings.card_template_name = filename
    settings.card_maker_enabled = enabled
    db.add(settings)
    template_row = db.get(CardTemplate, event.id) or CardTemplate(event_id=event.id)
    template_row.image_data = content
    db.add(template_row)
    db.commit()
    return {"ok": True, "filename": filename, "width": rgba.width, "height": rgba.height}


@router.get("/events")
def list_cloud_events(offset: int = 0, limit: int = 100, db: Session = Depends(get_db), _: None = Depends(require_sync_token)):
    offset = max(0, offset)
    limit = min(max(1, limit), 200)
    events = db.query(Event).order_by(Event.updated_at.desc()).offset(offset).limit(limit).all()
    result = []
    for event in events:
        result.append(event_out(event, db.get(GallerySettings, event.id)))
    return result


@router.get("/events/{public_id}/photos")
def list_cloud_event_photos(public_id: str, offset: int = 0, limit: int = 200, db: Session = Depends(get_db), _: None = Depends(require_sync_token)):
    event = db.query(Event).filter(Event.public_id == public_id).first()
    if not event:
        raise HTTPException(404, "Event not found")
    offset = max(0, offset)
    limit = min(max(1, limit), 500)
    photos = db.query(Photo).filter(Photo.event_id == event.id).order_by(Photo.id.asc()).offset(offset).limit(limit).all()
    return [
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
        for photo in photos
    ]


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
