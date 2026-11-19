from __future__ import annotations

import hashlib
import hmac
import os
import time
import tempfile
from threading import Lock
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from sqlalchemy.orm import Session
import qrcode

from ..database import get_db
from ..models import Event, GallerySettings, Photo, PhotoVariant

router = APIRouter(prefix="/api/gallery", tags=["gallery"])
PIN_COOKIE = "momentlink_gallery_access"
PIN_TTL_SECONDS = 12 * 60 * 60
PIN_ATTEMPTS = 8
PIN_WINDOW_SECONDS = 300
MAX_PHOTO_BYTES = 100 * 1024 * 1024
_pin_failures: dict[tuple[str, str], list[float]] = {}
_pin_failures_lock = Lock()


def pin_ok(event: Event, pin: str = "") -> bool:
    if not event.pin_hash:
        return True
    supplied = hashlib.sha256(pin.strip().encode("utf-8")).hexdigest()
    return hmac.compare_digest(event.pin_hash, supplied)


def require_gallery_access(event: Event, pin: str = "") -> None:
    if not pin_ok(event, pin):
        raise HTTPException(403, "Gallery PIN is required")


def pin_cookie_value(public_id: str, pin_hash_value: str) -> str:
    expires = str(int(time.time()) + PIN_TTL_SECONDS)
    body = f"{public_id}:{expires}"
    signature = hmac.new(pin_hash_value.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{expires}.{signature}"


def cookie_pin_ok(event: Event, token: str) -> bool:
    try:
        expires, signature = token.split(".", 1)
        if len(signature) != 64:
            return False
        if int(expires) < int(time.time()):
            return False
        body = f"{event.public_id}:{expires}"
        expected = hmac.new(event.pin_hash.encode(), body.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)
    except (ValueError, TypeError):
        return False


def has_gallery_access(event: Event, request: Request) -> bool:
    if not event.pin_hash:
        return True
    return cookie_pin_ok(event, request.cookies.get(PIN_COOKIE, ""))


def check_pin_rate(request: Request, public_id: str) -> int:
    key = (request.client.host if request.client else "unknown", public_id)
    now = time.monotonic()
    with _pin_failures_lock:
        attempts = [stamp for stamp in _pin_failures.get(key, []) if now - stamp < PIN_WINDOW_SECONDS]
        _pin_failures[key] = attempts
        if len(attempts) >= PIN_ATTEMPTS:
            return max(1, int(PIN_WINDOW_SECONDS - (now - attempts[0])))
    return 0


def record_pin_failure(request: Request, public_id: str) -> None:
    key = (request.client.host if request.client else "unknown", public_id)
    now = time.monotonic()
    with _pin_failures_lock:
        attempts = [stamp for stamp in _pin_failures.get(key, []) if now - stamp < PIN_WINDOW_SECONDS]
        attempts.append(now)
        _pin_failures[key] = attempts


def grant_pin_access(event: Event, request: Request, response: Response, pin: str) -> bool:
    if not event.pin_hash:
        return True
    if cookie_pin_ok(event, request.cookies.get(PIN_COOKIE, "")):
        return True
    if not pin_ok(event, pin):
        return False
    is_https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    response.set_cookie(PIN_COOKIE, pin_cookie_value(event.public_id, event.pin_hash), max_age=PIN_TTL_SECONDS, httponly=True, secure=is_https, samesite="none" if is_https else "lax", path=f"/api/gallery/{event.public_id}")
    return True


@router.post("/{public_id}/unlock")
def unlock_gallery(public_id: str, payload: dict, request: Request, response: Response, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.public_id == public_id).first()
    if not event:
        raise HTTPException(404, "Gallery not found")
    settings = db.get(GallerySettings, event.id)
    if settings and not settings.enabled:
        raise HTTPException(404, "Gallery is closed")
    retry_after = check_pin_rate(request, public_id)
    if retry_after:
        raise HTTPException(429, "Too many incorrect PIN attempts", headers={"Retry-After": str(retry_after)})
    pin = payload.get("pin") if isinstance(payload, dict) else None
    if not isinstance(pin, str) or len(pin) > 64 or not grant_pin_access(event, request, response, pin):
        record_pin_failure(request, public_id)
        raise HTTPException(403, "Gallery PIN is incorrect")
    with _pin_failures_lock:
        _pin_failures.pop((request.client.host if request.client else "unknown", public_id), None)
    return {"ok": True}


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


def photo_download_url(request: Request, public_id: str, photo_id: str, pin: str = "") -> str:
    # Keep gallery downloads same-origin so the Vercel API rewrite can proxy
    # them and the browser never needs cross-site CORS for protected media.
    return f"/api/gallery/{public_id}/photos/{photo_id}/download"


def finished_variant(rows: list[PhotoVariant]) -> PhotoVariant | None:
    by_kind = {row.kind: row for row in rows}
    result = by_kind.get("finished")
    if result:
        return result
    return by_kind.get("preview") or by_kind.get("thumbnail")


def variant_url(variant: PhotoVariant, requested_kind: str | None = None) -> str:
    if variant.storage_provider == "google_drive":
        kind = requested_kind or variant.kind
        if kind == "finished":
            return drive_download_url(variant.storage_object_id)
        return drive_preview_url(variant.storage_object_id, 1600 if kind == "preview" else 500)
    return variant.storage_object_id


def variants_for_photo(db: Session, photo: Photo, download_url: str = "", rows: list[PhotoVariant] | None = None) -> list[dict]:
    if rows is None:
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
            url = download_url if kind == "finished" and download_url else variant_url(variant, kind)
            result.append({"kind": kind, "url": url, "drive_id": variant.storage_object_id if variant.storage_provider == "google_drive" else ""})
    return result


@router.get("/{public_id}")
def gallery(public_id: str, request: Request, db: Session = Depends(get_db), response: Response = None):
    if response:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    event = db.query(Event).filter(Event.public_id == public_id).first()
    if not event:
        raise HTTPException(404, "Gallery not found")
    settings = db.get(GallerySettings, event.id)
    if settings and not settings.enabled:
        raise HTTPException(404, "Gallery is closed")
    locked = not has_gallery_access(event, request)
    count = 0 if locked else db.query(Photo).filter(Photo.event_id == event.id, Photo.published == True, Photo.hidden == False).count()
    return {
        "event": {"name": event.name, "event_date": event.event_date, "photo_count": count, "gallery_url": public_gallery_url(event.public_id, request)},
        "settings": {
            "allow_download": settings.allow_download if settings else True,
            "find_my_photos": False,
            "credit_text": settings.credit_text if settings and settings.credit_text else "Photo Booth Experience by CS.BXXM STUDIO",
            "report_contact": settings.report_contact if settings else "",
            "locked": locked,
            "requires_pin": bool(event.pin_hash),
        },
    }


@router.get("/{public_id}/qr.png")
def gallery_qr(public_id: str, request: Request, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.public_id == public_id).first()
    if not event:
        raise HTTPException(404, "Gallery not found")
    settings = db.get(GallerySettings, event.id)
    if settings and not settings.enabled:
        raise HTTPException(404, "Gallery is closed")
    cache_key = hashlib.sha256(public_id.encode("utf-8")).hexdigest()[:32]
    path = Path(tempfile.gettempdir()) / f"momentlink_gallery_qr_{cache_key}.png"
    img = qrcode.make(public_gallery_url(public_id, request))
    img.save(path)
    return FileResponse(path, media_type="image/png")


@router.get("/{public_id}/photos")
def photos(public_id: str, request: Request, page: int = 1, page_size: int = 60, db: Session = Depends(get_db), response: Response = None):
    if response:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    event = db.query(Event).filter(Event.public_id == public_id).first()
    if not event:
        raise HTTPException(404, "Gallery not found")
    settings = db.get(GallerySettings, event.id)
    if settings and not settings.enabled:
        raise HTTPException(404, "Gallery is closed")
    if not has_gallery_access(event, request):
        require_gallery_access(event)
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    rows = db.query(Photo).filter(Photo.event_id == event.id, Photo.published == True, Photo.hidden == False).order_by(Photo.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    photo_ids = [photo.id for photo in rows]
    variants_by_photo: dict[str, list[PhotoVariant]] = {photo_id: [] for photo_id in photo_ids}
    if photo_ids:
        for variant in db.query(PhotoVariant).filter(PhotoVariant.photo_id.in_(photo_ids)).all():
            variants_by_photo.setdefault(variant.photo_id, []).append(variant)
    return [
        {
            "id": p.id,
            "filename": p.filename,
            "variants": variants_for_photo(
                db,
                p,
                photo_download_url(request, public_id, p.id),
                variants_by_photo.get(p.id, []),
            ),
        }
        for p in rows
    ]


@router.get("/{public_id}/photos/{photo_id}/download")
async def download_photo(public_id: str, photo_id: str, request: Request, response: Response, db: Session = Depends(get_db)):
    photo = (
        db.query(Photo)
        .join(Event, Event.id == Photo.event_id)
        .filter(
            Event.public_id == public_id,
            Photo.id == photo_id,
            Photo.published == True,
            Photo.hidden == False,
        )
        .first()
    )
    if not photo:
        raise HTTPException(404, "Photo not found")
    event = db.get(Event, photo.event_id)
    if not event:
        raise HTTPException(404, "Gallery not found")
    if not has_gallery_access(event, request):
        require_gallery_access(event)
    settings = db.get(GallerySettings, photo.event_id)
    if settings and not settings.enabled:
        raise HTTPException(404, "Gallery is closed")
    if settings and not settings.allow_download:
        raise HTTPException(403, "Downloads are disabled")
    variants = db.query(PhotoVariant).filter(
        PhotoVariant.photo_id == photo.id,
        PhotoVariant.kind.in_(["finished", "preview", "thumbnail"]),
    ).all()
    variants_by_kind = {row.kind: row for row in variants}
    selected = [variants_by_kind[kind] for kind in ("finished", "preview", "thumbnail") if kind in variants_by_kind]
    # Finished is the only full-resolution export. Use a smaller processed
    # preview as a fallback if it is missing; never fall back to the original.
    if "finished" in variants_by_kind:
        selected = [variants_by_kind["finished"], *[variants_by_kind[kind] for kind in ("preview", "thumbnail") if kind in variants_by_kind]]
    else:
        selected = [variants_by_kind[kind] for kind in ("preview", "thumbnail") if kind in variants_by_kind]
    download_variants = [variant for variant in selected if variant.storage_provider == "google_drive" and variant.storage_object_id]
    if not selected or not download_variants:
        raise HTTPException(404, "No processed photo variant is available")

    temp = tempfile.NamedTemporaryFile(prefix="momentlink-photo-", suffix=".jpg", delete=False)
    download_path = temp.name
    temp.close()
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(60, connect=15)) as client:
            download_ok = False
            last_storage_status = 0
            for variant in download_variants:
                try:
                    with open(download_path, "wb") as output:
                        total_bytes = 0
                        async with client.stream("GET", drive_download_url(variant.storage_object_id)) as upstream:
                            last_storage_status = upstream.status_code
                            if upstream.status_code >= 400 or upstream.headers.get("content-type", "").lower().startswith("text/html"):
                                continue
                            async for chunk in upstream.aiter_bytes(1024 * 1024):
                                total_bytes += len(chunk)
                                if total_bytes > MAX_PHOTO_BYTES:
                                    raise HTTPException(413, "Photo exceeds the 100 MB download limit")
                                output.write(chunk)
                    with open(download_path, "rb") as downloaded_file:
                        signature = downloaded_file.read(12)
                        if signature.startswith(b"\xff\xd8\xff") or signature[4:12] == b"ftypheic" or signature[4:12] == b"ftypheif":
                            download_ok = True
                            break
                except httpx.HTTPError:
                    continue
            if not download_ok:
                detail = f"File storage returned HTTP {last_storage_status}" if last_storage_status >= 400 else "Photo storage did not return a valid image"
                raise HTTPException(502, detail)
    except HTTPException:
        if os.path.exists(download_path):
            os.unlink(download_path)
        raise
    except httpx.HTTPError as exc:
        if os.path.exists(download_path):
            os.unlink(download_path)
        raise HTTPException(502, "Cannot download file from storage") from exc
    except Exception:
        if os.path.exists(download_path):
            os.unlink(download_path)
        raise

    filename = quote(photo.filename, safe="")
    ascii_filename = Path(photo.filename).name.encode("ascii", "ignore").decode("ascii") or "photoflow-photo.jpg"
    headers = {"Content-Disposition": f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{filename}'}
    return FileResponse(
        download_path,
        media_type="image/jpeg",
        headers=headers,
        background=BackgroundTask(os.unlink, download_path),
    )


@router.get("/{public_id}/downloads")
def download_links(public_id: str, request: Request, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.public_id == public_id).first()
    if not event:
        raise HTTPException(404, "Gallery not found")
    settings = db.get(GallerySettings, event.id)
    if settings and not settings.enabled:
        raise HTTPException(404, "Gallery is closed")
    if not has_gallery_access(event, request):
        require_gallery_access(event)
    if settings and not settings.allow_download:
        raise HTTPException(403, "Downloads are disabled")
    rows = db.query(Photo).filter(Photo.event_id == event.id, Photo.published == True, Photo.hidden == False).order_by(Photo.created_at.desc()).all()
    photo_ids = [photo.id for photo in rows]
    variants_by_photo: dict[str, list[PhotoVariant]] = {}
    if photo_ids:
        for variant in db.query(PhotoVariant).filter(
            PhotoVariant.photo_id.in_(photo_ids),
            PhotoVariant.kind.in_(["finished", "preview", "thumbnail"]),
        ).all():
            variants_by_photo.setdefault(variant.photo_id, []).append(variant)
    links = []
    for photo in rows:
        finished = finished_variant(variants_by_photo.get(photo.id, []))
        if finished:
            links.append({"filename": photo.filename, "url": photo_download_url(request, public_id, photo.id)})
    return {"event": event.name, "gallery_url": public_gallery_url(event.public_id, request), "links": links}
