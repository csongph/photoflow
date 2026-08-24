from __future__ import annotations

import json
from pathlib import Path

import qrcode
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Event, Photo, Upload
from ..utils.public_url import public_gallery_url

router = APIRouter(prefix="/api/gallery", tags=["local-gallery"])


def drive_download_url(file_id: str) -> str:
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def local_media_url(photo: Photo, variant: str, source_path: str) -> str:
    return f"/media/{photo.event_id}/{variant}/{Path(source_path).name}"


def event_by_public_id(db: Session, public_id: str) -> Event:
    event = db.query(Event).filter(Event.public_id == public_id).first()
    if not event:
        raise HTTPException(404, "Gallery not found")
    return event


def gallery_settings(event: Event) -> dict:
    return json.loads(event.gallery_json or "{}")


def gallery_pin(event: Event) -> str:
    return str(gallery_settings(event).get("optional_pin") or "").strip()


def pin_ok(event: Event, pin: str = "") -> bool:
    expected = gallery_pin(event)
    return not expected or pin == expected


def require_gallery_access(event: Event, pin: str = "") -> None:
    if not pin_ok(event, pin):
        raise HTTPException(403, "ต้องใส่ PIN ก่อนดูรูปใน Gallery นี้")


@router.get("/{public_id}")
def gallery(public_id: str, pin: str = "", db: Session = Depends(get_db)):
    event = event_by_public_id(db, public_id)
    settings = gallery_settings(event)
    locked = not pin_ok(event, pin)
    count = 0 if locked else db.query(Photo).filter(Photo.event_id == event.id, Photo.published == True, Photo.hidden == False).count()
    return {
        "event": {
            "name": event.name,
            "event_date": event.event_date,
            "photo_count": count,
            "gallery_url": public_gallery_url(db, event.public_id),
        },
        "settings": {
            "allow_download": settings.get("allow_download", True),
            "find_my_photos": settings.get("find_my_photos", True),
            "credit_text": settings.get("credit_text") or "ถ่ายภาพโดยทีมโสตโรงเรียน",
            "report_contact": settings.get("report_contact") or "",
            "locked": locked,
            "requires_pin": bool(gallery_pin(event)),
        },
    }


@router.get("/{public_id}/qr.png")
def gallery_qr(public_id: str, db: Session = Depends(get_db)):
    event = event_by_public_id(db, public_id)
    path = Path(event.root_path) / "CACHE" / "gallery_screen_qr.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    img = qrcode.make(public_gallery_url(db, event.public_id))
    img.save(path)
    return FileResponse(path, media_type="image/png")


@router.get("/{public_id}/photos")
def photos(public_id: str, page: int = 1, page_size: int = 60, pin: str = "", db: Session = Depends(get_db)):
    event = event_by_public_id(db, public_id)
    require_gallery_access(event, pin)
    rows = (
        db.query(Photo)
        .filter(Photo.event_id == event.id, Photo.published == True, Photo.hidden == False)
        .order_by(Photo.created_at.desc())
        .offset((max(page, 1) - 1) * page_size)
        .limit(min(max(page_size, 1), 100))
        .all()
    )
    result = []
    for photo in rows:
        variants = []
        uploaded = {u.variant: u for u in db.query(Upload).filter(Upload.photo_id == photo.id, Upload.state == "UPLOADED").all()}
        if photo.thumbnail_path:
            drive_id = uploaded.get("thumbnail").object_id if uploaded.get("thumbnail") else ""
            url = local_media_url(photo, "THUMBNAILS", photo.thumbnail_path)
            variants.append({"kind": "thumbnail", "url": url, "drive_id": uploaded.get("thumbnail").object_id if uploaded.get("thumbnail") else ""})
        if photo.preview_path:
            drive_id = uploaded.get("preview").object_id if uploaded.get("preview") else ""
            url = local_media_url(photo, "PREVIEWS", photo.preview_path)
            variants.append({"kind": "preview", "url": url, "drive_id": uploaded.get("preview").object_id if uploaded.get("preview") else ""})
        if photo.finished_path:
            drive_id = uploaded.get("finished").object_id if uploaded.get("finished") else ""
            url = drive_download_url(drive_id) if drive_id else local_media_url(photo, "FINISHED", photo.finished_path)
            variants.append({"kind": "finished", "url": url, "drive_id": drive_id})
        result.append({"id": photo.id, "filename": photo.filename, "variants": variants})
    return result


@router.get("/{public_id}/downloads")
def download_links(public_id: str, pin: str = "", db: Session = Depends(get_db)):
    event = event_by_public_id(db, public_id)
    require_gallery_access(event, pin)
    rows = db.query(Photo).filter(Photo.event_id == event.id, Photo.published == True, Photo.hidden == False).order_by(Photo.created_at.desc()).all()
    result = []
    for photo in rows:
        upload = db.query(Upload).filter(Upload.photo_id == photo.id, Upload.variant == "finished", Upload.state == "UPLOADED").first()
        if upload and upload.object_id:
            url = drive_download_url(upload.object_id)
        elif photo.finished_path:
            url = f"/media/{photo.event_id}/FINISHED/{Path(photo.finished_path).name}"
        else:
            continue
        result.append({"filename": photo.filename, "url": url})
    return {
        "event": event.name,
        "gallery_url": public_gallery_url(db, event.public_id),
        "links": result,
    }


@router.post("/{public_id}/find-my-photos")
async def find_my_photos(public_id: str, consent: bool = False, pin: str = "", file: UploadFile = File(...), db: Session = Depends(get_db)):
    event = event_by_public_id(db, public_id)
    require_gallery_access(event, pin)
    if not consent:
        raise HTTPException(400, "ต้องยินยอมก่อนอัปโหลดภาพเพื่อค้นหา")
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(400, "ชนิดไฟล์ภาพไม่รองรับ")
    data = await file.read()
    if len(data) > 8_000_000:
        raise HTTPException(400, "ไฟล์ภาพใหญ่เกินไป")
    return {
        "status": "NEEDS_FACE_ENGINE",
        "message": "โหมด Find My Photos ต้องตั้งค่า face engine/cloud ก่อน ตอนนี้ gallery ยังดูรูปได้ตามปกติ",
    }
