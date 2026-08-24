from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Event, FaceSearchSession, GallerySettings, Photo, PhotoVariant

router = APIRouter(prefix="/api/gallery", tags=["gallery"])


@router.get("/{public_id}")
def gallery(public_id: str, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.public_id == public_id).first()
    if not event:
        raise HTTPException(404, "Gallery not found")
    settings = db.get(GallerySettings, event.id)
    count = db.query(Photo).filter(Photo.event_id == event.id, Photo.published == True, Photo.hidden == False).count()
    return {"event": {"name": event.name, "event_date": event.event_date, "photo_count": count}, "settings": {"allow_download": settings.allow_download if settings else True, "find_my_photos": settings.find_my_photos if settings else True}}


@router.get("/{public_id}/photos")
def photos(public_id: str, page: int = 1, page_size: int = 60, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.public_id == public_id).first()
    if not event:
        raise HTTPException(404, "Gallery not found")
    rows = db.query(Photo).filter(Photo.event_id == event.id, Photo.published == True, Photo.hidden == False).order_by(Photo.created_at.desc()).offset((page - 1) * page_size).limit(min(page_size, 100)).all()
    return [{"id": p.id, "filename": p.filename, "variants": []} for p in rows]


@router.post("/{public_id}/find-my-photos")
async def find_my_photos(public_id: str, consent: bool = False, file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not consent:
        raise HTTPException(400, "Explicit consent is required")
    event = db.query(Event).filter(Event.public_id == public_id).first()
    if not event:
        raise HTTPException(404, "Gallery not found")
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(400, "Unsupported image type")
    data = await file.read()
    if len(data) > 8_000_000:
        raise HTTPException(400, "Image is too large")
    session = FaceSearchSession(id=secrets.token_urlsafe(24), event_id=event.id, status="PENDING")
    db.add(session)
    db.commit()
    return {"session_id": session.id, "status": "PENDING", "message": "Possible Matches will appear when face search is configured."}

