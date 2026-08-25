from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Event, GallerySettings, Photo, PhotoVariant

router = APIRouter(prefix="/api/sync", tags=["sync"])


def require_sync_token(authorization: str = Header("")) -> None:
    expected = os.getenv("CLOUD_SYNC_TOKEN", "").strip()
    if not expected:
        return
    if authorization != f"Bearer {expected}":
        raise HTTPException(401, "Invalid sync token")


@router.post("/event")
def sync_event(payload: dict, db: Session = Depends(get_db), _: None = Depends(require_sync_token)):
    event = db.query(Event).filter(Event.public_id == payload["public_id"]).first() or Event(public_id=payload["public_id"])
    event.name = payload["name"]
    event.event_date = payload.get("event_date", "")
    event.description = payload.get("description", "")
    db.add(event)
    db.flush()
    allowed = {"allow_download", "find_my_photos", "auto_refresh", "credit_text", "report_contact"}
    gallery_settings = {k: v for k, v in payload.get("gallery_settings", {}).items() if k in allowed}
    db.merge(GallerySettings(event_id=event.id, **gallery_settings))
    db.commit()
    return {"event_id": event.id, "public_id": event.public_id}


@router.post("/photo")
def sync_photo(payload: dict, db: Session = Depends(get_db), _: None = Depends(require_sync_token)):
    event = db.query(Event).filter(Event.public_id == payload["public_id"]).first()
    if not event:
        return {"error": "event_not_found"}
    photo = db.query(Photo).filter(Photo.event_id == event.id, Photo.local_photo_id == payload["local_photo_id"]).first()
    if not photo:
        photo = Photo(event_id=event.id, local_photo_id=payload["local_photo_id"])
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
