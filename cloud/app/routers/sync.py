from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Event, GallerySettings, Photo, PhotoVariant

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("/event")
def sync_event(payload: dict, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.public_id == payload["public_id"]).first() or Event(public_id=payload["public_id"])
    event.name = payload["name"]
    event.event_date = payload.get("event_date", "")
    event.description = payload.get("description", "")
    db.add(event)
    db.flush()
    db.merge(GallerySettings(event_id=event.id, **payload.get("gallery_settings", {})))
    db.commit()
    return {"event_id": event.id, "public_id": event.public_id}


@router.post("/photo")
def sync_photo(payload: dict, db: Session = Depends(get_db)):
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
        db.add(PhotoVariant(photo_id=photo.id, **variant))
    db.commit()
    return {"photo_id": photo.id}

