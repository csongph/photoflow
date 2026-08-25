from __future__ import annotations

import os
import secrets
import tempfile
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import qrcode

from ..database import get_db
from ..models import Event, FaceSearchSession, GallerySettings, Photo, PhotoVariant

router = APIRouter(prefix="/api/gallery", tags=["gallery"])


def request_base_url(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("host", "").strip()
    return f"{proto}://{host}" if host else str(request.base_url).rstrip("/")


def public_gallery_url(public_id: str, request: Request | None = None) -> str:
    base = os.getenv("PUBLIC_GALLERY_BASE_URL", "").rstrip("/")
    if not base:
        base = f"{request_base_url(request)}/gallery" if request else "/gallery"
    if base.startswith(("http://", "https://")):
        parts = urlsplit(base)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query["event"] = public_id
        return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", urlencode(query), parts.fragment))
    return f"{base}/{public_id}"


def drive_download_url(file_id: str) -> str:
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def drive_preview_url(file_id: str, size: int = 1600) -> str:
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w{size}"


def variant_url(variant: PhotoVariant) -> str:
    if variant.storage_provider == "google_drive":
        if variant.kind == "finished":
            return drive_download_url(variant.storage_object_id)
        return drive_preview_url(variant.storage_object_id, 1600 if variant.kind == "preview" else 500)
    return variant.storage_object_id


def variants_for_photo(db: Session, photo: Photo) -> list[dict]:
    rows = db.query(PhotoVariant).filter(PhotoVariant.photo_id == photo.id).all()
    by_kind = {row.kind: row for row in rows}
    finished = by_kind.get("finished")
    if finished:
        by_kind.setdefault("preview", finished)
        by_kind.setdefault("thumbnail", finished)
    result = []
    for kind in ["thumbnail", "preview", "finished"]:
        variant = by_kind.get(kind)
        if variant:
            result.append({"kind": kind, "url": variant_url(variant), "drive_id": variant.storage_object_id if variant.storage_provider == "google_drive" else ""})
    return result


@router.get("/{public_id}")
def gallery(public_id: str, request: Request, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.public_id == public_id).first()
    if not event:
        raise HTTPException(404, "Gallery not found")
    settings = db.get(GallerySettings, event.id)
    count = db.query(Photo).filter(Photo.event_id == event.id, Photo.published == True, Photo.hidden == False).count()
    return {
        "event": {"name": event.name, "event_date": event.event_date, "photo_count": count, "gallery_url": public_gallery_url(event.public_id, request)},
        "settings": {
            "allow_download": settings.allow_download if settings else True,
            "find_my_photos": settings.find_my_photos if settings else True,
            "credit_text": settings.credit_text if settings and settings.credit_text else "ถ่ายภาพโดยทีมโสตโรงเรียน",
            "report_contact": settings.report_contact if settings else "",
            "locked": False,
            "requires_pin": False,
        },
    }


@router.get("/{public_id}/qr.png")
def gallery_qr(public_id: str, request: Request):
    path = Path(tempfile.gettempdir()) / f"momentlink_gallery_qr_{public_id}.png"
    img = qrcode.make(public_gallery_url(public_id, request))
    img.save(path)
    return FileResponse(path, media_type="image/png")


@router.get("/{public_id}/photos")
def photos(public_id: str, page: int = 1, page_size: int = 60, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.public_id == public_id).first()
    if not event:
        raise HTTPException(404, "Gallery not found")
    rows = db.query(Photo).filter(Photo.event_id == event.id, Photo.published == True, Photo.hidden == False).order_by(Photo.created_at.desc()).offset((page - 1) * page_size).limit(min(page_size, 100)).all()
    return [{"id": p.id, "filename": p.filename, "variants": variants_for_photo(db, p)} for p in rows]


@router.get("/{public_id}/downloads")
def download_links(public_id: str, request: Request, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.public_id == public_id).first()
    if not event:
        raise HTTPException(404, "Gallery not found")
    rows = db.query(Photo).filter(Photo.event_id == event.id, Photo.published == True, Photo.hidden == False).order_by(Photo.created_at.desc()).all()
    links = []
    for photo in rows:
        finished = db.query(PhotoVariant).filter(PhotoVariant.photo_id == photo.id, PhotoVariant.kind == "finished").first()
        if finished:
            links.append({"filename": photo.filename, "url": variant_url(finished)})
    return {"event": event.name, "gallery_url": public_gallery_url(event.public_id, request), "links": links}


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
