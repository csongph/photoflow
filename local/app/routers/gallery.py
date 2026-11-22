from __future__ import annotations

import json
import hashlib
import hmac
import os
import time
from datetime import timezone
from threading import Lock
from pathlib import Path

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Event, Photo, Upload
from ..utils.public_url import public_gallery_url

router = APIRouter(prefix="/api/gallery", tags=["local-gallery"])
PIN_COOKIE = "momentlink_gallery_access"
PIN_TTL_SECONDS = 12 * 60 * 60
PIN_ATTEMPTS = 8
PIN_WINDOW_SECONDS = 300
_pin_failures: dict[tuple[str, str], list[float]] = {}
_pin_failures_lock = Lock()
def drive_download_url(file_id: str) -> str:
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def local_media_url(photo: Photo, variant: str, source_path: str) -> str:
    return f"/media/{photo.event_id}/{variant}/{Path(source_path).name}"


def event_by_public_id(db: Session, public_id: str) -> Event:
    event = db.query(Event).filter(Event.public_id == public_id).first()
    if not event:
        raise HTTPException(404, "Gallery not found")
    try:
        enabled = json.loads(event.gallery_json or "{}").get("enable_gallery", True)
    except json.JSONDecodeError:
        enabled = True
    if not enabled:
        raise HTTPException(404, "Gallery is closed")
    return event


def gallery_settings(event: Event) -> dict:
    return json.loads(event.gallery_json or "{}")


def gallery_pin(event: Event) -> str:
    return str(gallery_settings(event).get("optional_pin") or "").strip()


def pin_ok(event: Event, pin: str = "") -> bool:
    expected = gallery_pin(event)
    return not expected or hmac.compare_digest(pin, expected)


def pin_cookie_value(event: Event) -> str:
    expires = str(int(time.time()) + PIN_TTL_SECONDS)
    secret = hashlib.sha256(event.id.encode()).hexdigest()
    payload = f"{event.public_id}:{expires}"
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{expires}.{signature}"


def cookie_pin_ok(event: Event, request: Request) -> bool:
    try:
        expires, signature = request.cookies.get(PIN_COOKIE, "").split(".", 1)
        if len(signature) != 64:
            return False
        if int(expires) < int(time.time()):
            return False
        secret = hashlib.sha256(event.id.encode()).hexdigest()
        payload = f"{event.public_id}:{expires}"
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)
    except (ValueError, TypeError):
        return False


def has_gallery_access(event: Event, request: Request) -> bool:
    if not gallery_pin(event):
        return True
    return cookie_pin_ok(event, request)


def check_pin_rate(request: Request, public_id: str) -> int:
    key = (request.client.host if request.client else "unknown", public_id)
    now = time.monotonic()
    with _pin_failures_lock:
        attempts = [stamp for stamp in _pin_failures.get(key, []) if now - stamp < PIN_WINDOW_SECONDS]
        _pin_failures[key] = attempts
        return max(1, int(PIN_WINDOW_SECONDS - (now - attempts[0]))) if len(attempts) >= PIN_ATTEMPTS else 0


def record_pin_failure(request: Request, public_id: str) -> None:
    key = (request.client.host if request.client else "unknown", public_id)
    now = time.monotonic()
    with _pin_failures_lock:
        attempts = [stamp for stamp in _pin_failures.get(key, []) if now - stamp < PIN_WINDOW_SECONDS]
        attempts.append(now)
        _pin_failures[key] = attempts


def grant_pin_access(event: Event, request: Request, response: Response, pin: str) -> bool:
    if not gallery_pin(event):
        return True
    if cookie_pin_ok(event, request):
        return True
    if not pin_ok(event, pin):
        return False
    response.set_cookie(PIN_COOKIE, pin_cookie_value(event), max_age=PIN_TTL_SECONDS, httponly=True, secure=request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https", samesite="lax", path=f"/api/gallery/{event.public_id}")
    return True


@router.post("/{public_id}/unlock")
def unlock_gallery(public_id: str, payload: dict, request: Request, response: Response, db: Session = Depends(get_db)):
    event = event_by_public_id(db, public_id)
    retry_after = check_pin_rate(request, public_id)
    if retry_after:
        raise HTTPException(429, "ลองใส่ PIN ผิดหลายครั้ง กรุณารอสักครู่", headers={"Retry-After": str(retry_after)})
    pin = payload.get("pin") if isinstance(payload, dict) else None
    if not isinstance(pin, str) or len(pin) > 64 or not grant_pin_access(event, request, response, pin):
        record_pin_failure(request, public_id)
        raise HTTPException(403, "PIN ไม่ถูกต้อง")
    with _pin_failures_lock:
        _pin_failures.pop((request.client.host if request.client else "unknown", public_id), None)
    return {"ok": True}


def require_gallery_access(event: Event, pin: str = "") -> None:
    if not pin_ok(event, pin):
        raise HTTPException(403, "ต้องใส่ PIN ก่อนดูรูปใน Gallery นี้")


@router.get("/{public_id}")
def gallery(public_id: str, request: Request, db: Session = Depends(get_db), response: Response = None):
    if response:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    event = event_by_public_id(db, public_id)
    settings = gallery_settings(event)
    locked = not has_gallery_access(event, request)
    strip = settings.get("photo_strip") if isinstance(settings.get("photo_strip"), dict) else {}
    strip_themes = strip.get("themes") if isinstance(strip.get("themes"), list) else []
    active_strip_theme = next((theme for theme in strip_themes if isinstance(theme, dict) and theme.get("id") == strip.get("active_theme_id")), None)
    if active_strip_theme:
        layouts = active_strip_theme.get("layouts") if isinstance(active_strip_theme.get("layouts"), dict) else {}
        for count in (2, 3, 4):
            layout = layouts.get(str(count)) if isinstance(layouts.get(str(count)), dict) else {}
            layout["asset_present"] = (Path(event.root_path) / "CACHE" / "photo-strip" / active_strip_theme["id"] / f"{count}.png").is_file()
            layouts[str(count)] = layout
        active_strip_theme["layouts"] = layouts
    strip_available = bool(active_strip_theme and all(active_strip_theme.get("layouts", {}).get(str(count), {}).get("asset_present") for count in (2, 3, 4)))
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
            "find_my_photos": False,
            "credit_text": settings.get("credit_text") or "Photo Booth Experience by CS.BXXM STUDIO",
            "report_contact": settings.get("report_contact") or "",
            "locked": locked,
            "requires_pin": bool(gallery_pin(event)),
        },
    }


@router.get("/{public_id}/card-template.png")
def card_template(public_id: str, request: Request, db: Session = Depends(get_db)):
    raise HTTPException(404, "Card maker is no longer supported")
    event = event_by_public_id(db, public_id)
    if not has_gallery_access(event, request):
        require_gallery_access(event)
    settings = gallery_settings(event)
    if not settings.get("card_maker_enabled") or not settings.get("allow_download", True):
        raise HTTPException(404, "Card maker is disabled")
    path = Path(event.root_path) / "CACHE" / "card-template.png"
    if not path.is_file():
        raise HTTPException(404, "Card template not found")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


@router.get("/{public_id}/qr.png")
def gallery_qr(public_id: str, db: Session = Depends(get_db)):
    event = event_by_public_id(db, public_id)
    path = Path(event.root_path) / "CACHE" / "gallery_screen_qr.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    img = qrcode.make(public_gallery_url(db, event.public_id))
    img.save(path)
    return FileResponse(path, media_type="image/png")


@router.get("/{public_id}/photos")
def photos(public_id: str, request: Request, page: int = 1, page_size: int = 60, db: Session = Depends(get_db), response: Response = None):
    if response:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    event = event_by_public_id(db, public_id)
    if not has_gallery_access(event, request):
        require_gallery_access(event)
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    rows = (
        db.query(Photo)
        .filter(Photo.event_id == event.id, Photo.published == True, Photo.hidden == False)
        .order_by(Photo.created_at.desc(), Photo.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    photo_ids = [photo.id for photo in rows]
    uploads_by_photo: dict[str, dict[str, Upload]] = {photo_id: {} for photo_id in photo_ids}
    if photo_ids:
        for upload in db.query(Upload).filter(Upload.photo_id.in_(photo_ids), Upload.state == "UPLOADED").all():
            uploads_by_photo.setdefault(upload.photo_id, {})[upload.variant] = upload
    result = []
    for photo in rows:
        variants = []
        uploaded = uploads_by_photo.get(photo.id, {})
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
            url = f"/api/gallery/{public_id}/photos/{photo.id}/download"
            variants.append({"kind": "finished", "url": url, "drive_id": drive_id})
        created_at = photo.created_at
        if created_at and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        result.append({"id": photo.id, "filename": photo.filename, "created_at": created_at.isoformat() if created_at else "", "variants": variants})
    return result


@router.get("/{public_id}/photos/{photo_id}/download")
def download_photo(public_id: str, photo_id: str, request: Request, response: Response, db: Session = Depends(get_db)):
    event = event_by_public_id(db, public_id)
    if not has_gallery_access(event, request):
        require_gallery_access(event)
    if not gallery_settings(event).get("allow_download", True):
        raise HTTPException(403, "Downloads are disabled")
    photo = db.get(Photo, photo_id)
    if not photo or photo.event_id != event.id or not photo.published or photo.hidden:
        raise HTTPException(404, "Photo not found")
    # A few legacy or partially synced photos may only have a preview. Keep
    # their download button useful by returning the best available image.
    path = next(
        (
            Path(candidate)
            for candidate in (photo.finished_path, photo.preview_path, photo.thumbnail_path)
            if candidate and Path(candidate).is_file()
        ),
        None,
    )
    if not path:
        raise HTTPException(404, "Download file not found")
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "Download file not found")
    return FileResponse(path, filename=path.name, media_type="image/jpeg")


@router.get("/{public_id}/downloads")
def download_links(public_id: str, request: Request, db: Session = Depends(get_db)):
    event = event_by_public_id(db, public_id)
    if not has_gallery_access(event, request):
        require_gallery_access(event)
    if not gallery_settings(event).get("allow_download", True):
        raise HTTPException(403, "Downloads are disabled")
    rows = db.query(Photo).filter(Photo.event_id == event.id, Photo.published == True, Photo.hidden == False).order_by(Photo.created_at.desc(), Photo.id.desc()).all()
    result = []
    for photo in rows:
        path = next(
            (
                Path(candidate)
                for candidate in (photo.finished_path, photo.preview_path, photo.thumbnail_path)
                if candidate and Path(candidate).is_file()
            ),
            None,
        )
        if not path:
            continue
        url = f"/api/gallery/{public_id}/photos/{photo.id}/download"
        result.append({"filename": path.name, "url": url})
    return {
        "event": event.name,
        "gallery_url": public_gallery_url(db, event.public_id),
        "links": result,
    }


@router.get("/{public_id}/photo-strip/{theme_id}/{photo_count}.png")
def photo_strip_template(public_id: str, theme_id: str, photo_count: int, request: Request, db: Session = Depends(get_db)):
    raise HTTPException(404, "Photo Strip is no longer supported")
    event = event_by_public_id(db, public_id)
    if not has_gallery_access(event, request):
        require_gallery_access(event)
    settings = gallery_settings(event)
    strip = settings.get("photo_strip") if isinstance(settings.get("photo_strip"), dict) else {}
    if not strip.get("enabled") or not settings.get("allow_download", True):
        raise HTTPException(404, "Photo Strip is disabled")
    if photo_count not in (2, 3, 4) or theme_id != strip.get("active_theme_id"):
        raise HTTPException(404, "Photo Strip layout not found")
    theme = next((item for item in strip.get("themes", []) if isinstance(item, dict) and item.get("id") == theme_id), None)
    if not theme or not theme.get("layouts", {}).get(str(photo_count), {}).get("template_name"):
        raise HTTPException(404, "Photo Strip layout is not configured")
    path = Path(event.root_path) / "CACHE" / "photo-strip" / theme_id / f"{photo_count}.png"
    if not path.is_file():
        raise HTTPException(404, "Photo Strip layout asset not found")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "private, max-age=300"})
