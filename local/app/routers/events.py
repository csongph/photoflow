from __future__ import annotations

import json
import os
import secrets
import shutil
from datetime import datetime
from pathlib import Path

import qrcode
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from PIL import Image
from io import BytesIO
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Event, Job, Photo, Setting, Upload
from ..schemas.local import EventCreate, EventOut
from ..sync.cloud import CloudSyncError, delete_cloud_event, enabled as cloud_sync_enabled
from ..utils.files import atomic_json, safe_slug, sha256_file
from ..utils.local_paths import ensure_event_root
from ..utils.public_url import public_gallery_url
from ..watcher.service import watcher_manager

router = APIRouter(prefix="/api/events", tags=["events"])


EVENT_DIRS = ["INCOMING", "ORIGINAL", "PROCESSING", "FINISHED", "THUMBNAILS", "PREVIEWS", "FAILED", "CACHE"]


def gallery_url(db: Session, public_id: str) -> str:
    return public_gallery_url(db, public_id)


def enqueue_unique_job(db: Session, event_id: str, job_type: str, photo_id: str | None = None, priority: int = 60) -> None:
    pending = db.query(Job).filter(
        Job.event_id == event_id,
        Job.photo_id == photo_id,
        Job.type == job_type,
        Job.state.in_(["QUEUED", "RETRYING", "PROCESSING"]),
    ).first()
    if not pending:
        db.add(Job(event_id=event_id, photo_id=photo_id, type=job_type, priority=priority))


def to_out(db: Session, event: Event) -> EventOut:
    return EventOut(
        id=event.id,
        public_id=event.public_id,
        name=event.name,
        status=event.status,
        root_path=event.root_path,
        incoming_path=event.incoming_path,
        gallery_url=gallery_url(db, event.public_id),
    )


def event_drive_required(event: Event) -> bool:
    try:
        drive = json.loads(event.drive_json or "{}")
    except json.JSONDecodeError:
        drive = {}
    return bool(drive.get("upload_finished_photos"))


def gallery_settings(event: Event) -> dict:
    try:
        return json.loads(event.gallery_json or "{}")
    except json.JSONDecodeError:
        return {}


def can_publish_from_disk(photo: Photo) -> bool:
    return bool(photo.finished_path and photo.preview_path and photo.thumbnail_path)


def required_uploads_done(db: Session, photo_id: str) -> bool:
    return db.query(Upload).filter(
        Upload.photo_id == photo_id,
        Upload.variant == "finished",
        Upload.state == "UPLOADED",
        Upload.object_id != "",
    ).first() is not None


def ensure_photo(event_id: str, photo_id: str, db: Session) -> Photo:
    photo = db.get(Photo, photo_id)
    if not photo or photo.event_id != event_id:
        raise HTTPException(404, "Photo not found")
    return photo


def event_preflight(db: Session, event: Event) -> dict:
    checks: list[dict] = []
    incoming = Path(event.incoming_path)
    checks.append({"key": "incoming_folder", "ok": incoming.exists(), "required": True, "message": str(incoming)})
    if incoming.exists():
        try:
            probe = incoming / ".momentlink_preflight"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            checks.append({"key": "incoming_writable", "ok": True, "required": True, "message": "INCOMING is writable"})
        except OSError as exc:
            checks.append({"key": "incoming_writable", "ok": False, "required": True, "message": str(exc)})
        usage = shutil.disk_usage(incoming)
        checks.append({"key": "disk_space", "ok": usage.free > 2 * 1024 * 1024 * 1024, "required": True, "message": f"{round(usage.free / 1024 / 1024 / 1024, 1)} GB free"})

    public_url = gallery_url(db, event.public_id)
    local_only = "127.0.0.1" in public_url or "localhost" in public_url
    checks.append({"key": "public_gallery_url", "ok": not local_only, "required": True, "message": public_url})

    drive_required = event_drive_required(event)
    google_connected = bool(db.get(Setting, "google_refresh_token") and db.get(Setting, "google_refresh_token").value)
    checks.append({
        "key": "google_drive",
        "ok": google_connected if drive_required else True,
        "required": drive_required,
        "message": "connected" if google_connected else "not connected",
    })
    failed = [check for check in checks if check["required"] and not check["ok"]]
    return {"ok": not failed, "checks": checks, "failed": failed}


def read_event_payload(folder: Path) -> dict:
    marker = folder / "event.json"
    if not marker.exists():
        raise HTTPException(400, "event.json not found")
    try:
        return json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(400, f"Cannot read event.json: {exc}")


def import_finished_photos(db: Session, event: Event) -> int:
    root = Path(event.root_path)
    finished_dir = root / "FINISHED"
    if not finished_dir.exists():
        return 0
    count = 0
    for finished in sorted(finished_dir.glob("*")):
        if not finished.is_file() or finished.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue
        checksum = sha256_file(finished)
        if db.query(Photo).filter(Photo.event_id == event.id, Photo.checksum == checksum).first():
            continue
        thumb = root / "THUMBNAILS" / f"{finished.stem}.jpg"
        preview = root / "PREVIEWS" / f"{finished.stem}.jpg"
        original = root / "ORIGINAL" / finished.name
        photo = Photo(
            event_id=event.id,
            capture_id=finished.stem,
            filename=finished.name,
            original_path=str(original) if original.exists() else str(finished),
            checksum=checksum,
            file_size=finished.stat().st_size,
            mime_type="image/jpeg",
            status="QUEUED",
            published=False,
        )
        db.add(photo)
        db.flush()
        db.add(Job(event_id=event.id, photo_id=photo.id, type="PROCESS_PHOTO", priority=20))
        count += 1
    return count


def import_event_folder(db: Session, folder: Path) -> tuple[Event | None, int]:
    data = read_event_payload(folder)
    payload = data.get("event") or {}
    paths = data.get("paths") or {}
    event_id = str(data.get("id") or "").strip()
    public_id = str(data.get("public_id") or "").strip() or secrets.token_urlsafe(24)
    existing = db.get(Event, event_id) if event_id else None
    if existing:
        return existing, import_finished_photos(db, existing)
    if db.query(Event).filter(Event.public_id == public_id).first():
        public_id = secrets.token_urlsafe(24)
    name = str(payload.get("name") or folder.name).strip()
    event = Event(
        id=event_id or secrets.token_hex(16),
        public_id=public_id,
        name=name,
        description=str(payload.get("description") or ""),
        event_date=str(payload.get("event_date") or ""),
        slug=safe_slug(name),
        status="IMPORTED",
        root_path=str(folder),
        incoming_path=str(paths.get("incoming") or folder / "INCOMING"),
        preset_id="neutral",
        processing_profile="Passthrough",
        auto_correction_json="{}",
        gallery_json=json.dumps(payload.get("gallery") or {}),
        drive_json=json.dumps(payload.get("drive") or {}),
    )
    db.add(event)
    db.flush()
    return event, import_finished_photos(db, event)


def import_cloud_events(db: Session, rows: list[dict]) -> dict[str, int]:
    """Idempotently mirror cloud event/photo metadata without copying originals."""
    created = updated = photo_count = 0
    root = ensure_event_root(db)
    for remote in rows:
        public_id = str(remote.get("public_id") or "").strip()
        name = str(remote.get("name") or "").strip()
        if not public_id or not name or len(name) > 180:
            continue
        event = db.query(Event).filter(Event.public_id == public_id).first()
        if event and not gallery_settings(event).get("cloud_mirror"):
            continue
        if not event:
            slug = safe_slug(name)
            folder = root / f"cloud_{slug}_{secrets.token_hex(4)}"
            for dirname in EVENT_DIRS:
                (folder / dirname).mkdir(parents=True, exist_ok=True)
            event = Event(
                public_id=public_id,
                name=name,
                description=str(remote.get("description") or "")[:10000],
                event_date=str(remote.get("event_date") or "")[:20],
                slug=slug,
                status="CLOUD",
                root_path=str(folder),
                incoming_path=str(folder / "INCOMING"),
                preset_id="neutral",
                processing_profile="Passthrough",
                auto_correction_json="{}",
                gallery_json=json.dumps({"cloud_mirror": True, **(remote.get("gallery_settings") if isinstance(remote.get("gallery_settings"), dict) else {})}),
                drive_json="{}",
            )
            db.add(event)
            db.flush()
            atomic_json(folder / "event.json", {"id": event.id, "public_id": public_id, "event": {"name": name}, "paths": {"root": str(folder), "incoming": str(folder / "INCOMING")}, "source": "cloud"})
            created += 1
        else:
            event.name = name
            event.description = str(remote.get("description") or "")[:10000]
            event.event_date = str(remote.get("event_date") or "")[:20]
            settings_payload = remote.get("gallery_settings") if isinstance(remote.get("gallery_settings"), dict) else {}
            settings_payload["cloud_mirror"] = True
            event.gallery_json = json.dumps(settings_payload)
            updated += 1

        existing = {photo.capture_id: photo for photo in db.query(Photo).filter(Photo.event_id == event.id).all()}
        for item in remote.get("photos") if isinstance(remote.get("photos"), list) else []:
            if not isinstance(item, dict):
                continue
            capture_id = str(item.get("local_photo_id") or "").strip()[:220]
            filename = str(item.get("filename") or "").strip()[:260]
            if not capture_id or not filename:
                continue
            photo = existing.get(capture_id)
            if not photo:
                photo = Photo(event_id=event.id, capture_id=capture_id, filename=filename, checksum=secrets.token_hex(32), status="PUBLISHED" if item.get("published") else "CLOUD", published=item.get("published") is True, hidden=item.get("hidden") is True)
                db.add(photo)
                db.flush()
                photo_count += 1
            photo.storage_provider = str(item.get("storage_provider") or "")[:60]
            photo.storage_object_id = str(item.get("storage_object_id") or "")[:300]
    db.commit()
    return {"created": created, "updated": updated, "photos": photo_count}


@router.get("")
def list_events(db: Session = Depends(get_db)):
    events = db.query(Event).order_by(Event.created_at.desc()).all()
    return [to_out(db, e) for e in events]


@router.post("/sync-cloud")
def sync_cloud_now(db: Session = Depends(get_db)):
    from ..sync.cloud import CloudSyncError, list_cloud_events

    try:
        result = import_cloud_events(db, list_cloud_events(strict=True))
    except CloudSyncError as exc:
        raise HTTPException(502, f"ดึงรายการ Event จาก Cloud ไม่สำเร็จ: {exc}") from exc
    return {"ok": True, **result}


@router.get("/importable")
def importable_events(root_path: str = "", db: Session = Depends(get_db)):
    root = Path(root_path).expanduser() if root_path.strip() else ensure_event_root(db)
    if not root.exists() or not root.is_dir():
        raise HTTPException(404, "Root folder not found")
    rows = []
    for marker in sorted(root.glob("*/event.json")):
        folder = marker.parent
        try:
            data = read_event_payload(folder)
        except HTTPException:
            continue
        event_id = str(data.get("id") or "")
        payload = data.get("event") or {}
        exists = bool(event_id and db.get(Event, event_id))
        rows.append({
            "id": event_id,
            "name": str(payload.get("name") or folder.name),
            "path": str(folder),
            "exists": exists,
            "finished_photos": len([p for p in (folder / "FINISHED").glob("*") if p.is_file()]) if (folder / "FINISHED").exists() else 0,
        })
    return {"root_path": str(root), "events": rows}


@router.post("/import-local")
def import_local_events(payload: dict[str, str] | None = None, db: Session = Depends(get_db)):
    payload = payload or {}
    root = Path(payload.get("root_path") or "").expanduser() if (payload.get("root_path") or "").strip() else ensure_event_root(db)
    event_folder = (payload.get("event_folder") or "").strip()
    folders = [Path(event_folder).expanduser()] if event_folder else [marker.parent for marker in sorted(root.glob("*/event.json"))]
    imported = []
    for folder in folders:
        if not folder.exists():
            continue
        event, photos = import_event_folder(db, folder.resolve())
        if event:
            imported.append({"id": event.id, "name": event.name, "path": event.root_path, "photos": photos})
    db.commit()
    return {"ok": True, "imported": imported}


@router.post("", response_model=EventOut)
def create_event(payload: EventCreate, db: Session = Depends(get_db)):
    public_id = secrets.token_urlsafe(24)
    slug = safe_slug(payload.name)
    suffix = secrets.token_hex(4)
    root = ensure_event_root(db) / f"{slug}_{suffix}"
    for dirname in EVENT_DIRS:
        (root / dirname).mkdir(parents=True, exist_ok=True)

    event = Event(
        public_id=public_id,
        name=payload.name.strip(),
        description=payload.description,
        event_date=payload.event_date,
        slug=slug,
        root_path=str(root),
        incoming_path=str(root / "INCOMING"),
        preset_id="neutral",
        processing_profile="Passthrough",
        auto_correction_json="{}",
        gallery_json=payload.gallery.model_dump_json(),
        drive_json=payload.drive.model_dump_json(),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    atomic_json(
        root / "event.json",
        {
            "id": event.id,
            "public_id": event.public_id,
            "event": payload.model_dump(),
            "paths": {"root": event.root_path, "incoming": event.incoming_path},
            "gallery_url": gallery_url(db, event.public_id),
            "created_at": datetime.utcnow().isoformat() + "Z",
        },
    )
    make_qr(db, event)
    if cloud_sync_enabled():
        enqueue_unique_job(db, event.id, "SYNC_EVENT", priority=40)
        db.commit()
    return to_out(db, event)


@router.post("/{event_id}/photobooth-frame")
async def upload_photobooth_frame(
    event_id: str,
    frame: UploadFile = File(...),
    orientation: str = "landscape",
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    if orientation not in {"landscape", "portrait"}:
        raise HTTPException(422, "Frame orientation must be landscape or portrait")
    if not (frame.filename or "").lower().endswith(".png"):
        raise HTTPException(415, "กรอบโฟโต้บูทต้องเป็นไฟล์ PNG ที่มีพื้นหลังโปร่งใส")
    content = await frame.read(20 * 1024 * 1024 + 1)
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(413, "ไฟล์กรอบต้องมีขนาดไม่เกิน 20 MB")
    try:
        with Image.open(BytesIO(content)) as source:
            if source.format != "PNG":
                raise HTTPException(415, "รองรับเฉพาะไฟล์ PNG")
            source.load()
            rgba = source.convert("RGBA")
            if min(rgba.getchannel("A").getextrema()) == 255:
                raise HTTPException(422, "PNG ต้องมีส่วนโปร่งใสเพื่อให้เห็นภาพถ่ายด้านใน")
            if rgba.width < 300 or rgba.height < 300 or rgba.width > 8000 or rgba.height > 8000:
                raise HTTPException(422, "ขนาดกรอบต้องอยู่ระหว่าง 300 ถึง 8000 พิกเซลต่อด้าน")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, "อ่านไฟล์ PNG ไม่ได้ กรุณาเลือกไฟล์กรอบที่ถูกต้อง") from exc

    frame_path = Path(event.root_path) / "CACHE" / f"photobooth-frame-{orientation}.png"
    frame_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = frame_path.with_suffix(".tmp.png")
    rgba.save(temp_path, format="PNG", optimize=True)
    temp_path.replace(frame_path)
    gallery = gallery_settings(event)
    gallery["photobooth_frame_enabled"] = True
    event.gallery_json = json.dumps(gallery)
    if cloud_sync_enabled():
        enqueue_unique_job(db, event.id, "SYNC_EVENT", priority=40)
    db.commit()
    return {"ok": True, "orientation": orientation, "filename": frame_path.name, "width": rgba.width, "height": rgba.height}


@router.post("/{event_id}/start")
def start_event(event_id: str, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    preflight = event_preflight(db, event)
    if not preflight["ok"]:
        raise HTTPException(400, {"message": "Preflight check failed", "checks": preflight["checks"]})
    usage = shutil.disk_usage(Path(event.incoming_path))
    warning = ""
    if usage.free < 2 * 1024 * 1024 * 1024:
        warning = "Disk space is low."
    event.status = "LIVE"
    db.commit()
    watcher_manager.start_event(event)
    return {"ok": True, "warning": warning}


@router.get("/{event_id}/preflight")
def preflight(event_id: str, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    return event_preflight(db, event)


@router.post("/{event_id}/pause-publishing")
def pause_publishing(event_id: str, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    event.publishing_paused = not event.publishing_paused
    db.commit()
    return {"paused": event.publishing_paused}


@router.post("/{event_id}/drive-requirement")
def update_drive_requirement(event_id: str, payload: dict[str, bool], db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    try:
        drive = json.loads(event.drive_json or "{}")
    except json.JSONDecodeError:
        drive = {}
    drive["upload_finished_photos"] = bool(payload.get("upload_finished_photos"))
    event.drive_json = json.dumps(drive)
    db.commit()
    return {"ok": True, "drive": drive}


@router.get("/{event_id}/gallery-settings")
def get_gallery_settings(event_id: str, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    settings = gallery_settings(event)
    return {
        "credit_text": settings.get("credit_text") or "ถ่ายภาพโดยทีมโสตโรงเรียน",
        "report_contact": settings.get("report_contact") or "",
    }


@router.post("/{event_id}/gallery-settings")
def update_gallery_settings(event_id: str, payload: dict[str, str], db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    settings = gallery_settings(event)
    settings["credit_text"] = str(payload.get("credit_text") or "ถ่ายภาพโดยทีมโสตโรงเรียน").strip()
    settings["report_contact"] = str(payload.get("report_contact") or "").strip()
    event.gallery_json = json.dumps(settings)
    if cloud_sync_enabled():
        enqueue_unique_job(db, event.id, "SYNC_EVENT", priority=40)
    db.commit()
    return {"ok": True, "gallery": settings}


@router.post("/{event_id}/end")
def end_event(event_id: str, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    watcher_manager.stop_event(event.id)
    event.status = "ENDED"
    db.commit()
    return {"ok": True}


@router.delete("/{event_id}")
def delete_event(event_id: str, delete_files: bool = Query(False), db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")

    # Clear the public URL before removing local data. This fails closed if
    # the cloud still serves the gallery, while retrying a timed-out delete is safe.
    if cloud_sync_enabled():
        try:
            delete_cloud_event(event.public_id, strict=True)
        except CloudSyncError as exc:
            raise HTTPException(502, f"ยังยืนยันการปิด Gallery ออนไลน์ไม่ได้: {exc}") from exc

    watcher_manager.stop_event(event.id)
    root = Path(event.root_path).resolve()
    folder_deleted = False
    folder_warning = ""

    db.query(Upload).filter(Upload.event_id == event.id).delete(synchronize_session=False)
    db.delete(event)
    db.commit()

    if delete_files:
        marker = root / "event.json"
        if not root.exists():
            folder_warning = "Event folder was already missing."
        elif not root.is_dir() or not marker.exists():
            folder_warning = "Skipped folder delete because this path does not look like a MomentLink event folder."
        else:
            try:
                shutil.rmtree(root)
                folder_deleted = True
            except OSError as exc:
                folder_warning = f"Database deleted, but folder delete failed: {exc}"

    return {"ok": True, "deleted_files": folder_deleted, "warning": folder_warning}


@router.post("/{event_id}/open-folder")
def open_event_folder(event_id: str, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    path = Path(event.root_path).resolve()
    if not path.exists():
        raise HTTPException(404, "Event folder not found")
    try:
        os.startfile(path)  # type: ignore[attr-defined]
    except AttributeError:
        raise HTTPException(400, "Open Folder is available on Windows local runs")
    except OSError as exc:
        raise HTTPException(500, f"Could not open folder: {exc}")
    return {"ok": True}


@router.post("/{event_id}/simulate-photo")
def simulate_photo(event_id: str, db: Session = Depends(get_db)):
    if os.getenv("ENABLE_DEMO_TOOLS", "false").strip().lower() != "true":
        raise HTTPException(404, "Demo tools are disabled")
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    from PIL import Image, ImageDraw

    incoming = Path(event.incoming_path)
    incoming.mkdir(parents=True, exist_ok=True)
    filename = f"SIM_{datetime.utcnow().strftime('%H%M%S')}.jpg"
    path = incoming / filename
    img = Image.new("RGB", (2200, 1450), (38, 41, 45))
    draw = ImageDraw.Draw(img)
    draw.rectangle((100, 100, 2100, 1350), outline=(230, 230, 220), width=10)
    draw.text((180, 180), f"MomentLink Demo\n{event.name}\n{filename}", fill=(245, 245, 235))
    img.save(path, "JPEG", quality=94)
    return {"ok": True, "path": str(path)}


@router.get("/{event_id}/photos")
def event_photos(event_id: str, db: Session = Depends(get_db)):
    photos = db.query(Photo).filter(Photo.event_id == event_id).order_by(Photo.created_at.desc()).limit(200).all()
    return [
        {
            "id": p.id,
            "filename": p.filename,
            "status": p.status,
            "published": p.published,
            "hidden": p.hidden,
            "error": p.error,
            "thumbnail": f"/media/{p.event_id}/THUMBNAILS/{Path(p.thumbnail_path).name}" if p.thumbnail_path else "",
            "preview": f"/media/{p.event_id}/PREVIEWS/{Path(p.preview_path).name}" if p.preview_path else "",
            "finished": f"/media/{p.event_id}/FINISHED/{Path(p.finished_path).name}" if p.finished_path else "",
        }
        for p in photos
    ]


@router.post("/{event_id}/photos/{photo_id}/publish")
def publish_photo(event_id: str, photo_id: str, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    photo = ensure_photo(event_id, photo_id, db)
    if not can_publish_from_disk(photo):
        raise HTTPException(400, "Photo is not processed yet")
    if event_drive_required(event) and not required_uploads_done(db, photo.id):
        raise HTTPException(400, "Google Drive uploads are not complete for this photo")
    photo.published = True
    photo.hidden = False
    photo.status = "PUBLISHED"
    photo.error = ""
    if cloud_sync_enabled():
        enqueue_unique_job(db, event.id, "SYNC_PHOTO", photo.id, 60)
    db.commit()
    return {"ok": True, "photo_id": photo.id, "published": True}


@router.post("/{event_id}/photos/publish-all")
def publish_all_photos(event_id: str, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    published = 0
    blocked = 0
    photos = db.query(Photo).filter(Photo.event_id == event_id, Photo.hidden == False).all()
    for photo in photos:
        if not can_publish_from_disk(photo):
            blocked += 1
            continue
        if event_drive_required(event) and not required_uploads_done(db, photo.id):
            blocked += 1
            continue
        photo.published = True
        photo.hidden = False
        photo.status = "PUBLISHED"
        photo.error = ""
        if cloud_sync_enabled():
            enqueue_unique_job(db, event.id, "SYNC_PHOTO", photo.id, 60)
        published += 1
    db.commit()
    return {"ok": True, "published": published, "blocked": blocked}


@router.post("/{event_id}/photos/{photo_id}/visibility")
def update_photo_visibility(event_id: str, photo_id: str, payload: dict[str, bool], db: Session = Depends(get_db)):
    photo = ensure_photo(event_id, photo_id, db)
    hidden = bool(payload.get("hidden"))
    photo.hidden = hidden
    if hidden and photo.published:
        photo.status = "HIDDEN"
    elif photo.published:
        photo.status = "PUBLISHED"
    elif can_publish_from_disk(photo):
        photo.status = "AWAITING_REVIEW" if gallery_settings(photo.event).get("review_before_publish") else "PROCESSED"
    if cloud_sync_enabled():
        enqueue_unique_job(db, photo.event_id, "SYNC_PHOTO", photo.id, 60)
    db.commit()
    return {"ok": True, "photo_id": photo.id, "hidden": photo.hidden}


@router.post("/{event_id}/photos/{photo_id}/reprocess")
def reprocess_photo(event_id: str, photo_id: str, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    photo = ensure_photo(event_id, photo_id, db)
    if not photo.original_path or not Path(photo.original_path).exists():
        raise HTTPException(400, "Original file is missing")
    photo.status = "QUEUED"
    photo.error = ""
    photo.published = False
    db.add(Job(event_id=event.id, photo_id=photo.id, type="PROCESS_PHOTO", priority=10))
    db.commit()
    return {"ok": True, "photo_id": photo.id}


@router.post("/{event_id}/photos/reprocess")
def reprocess_photos(event_id: str, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    count = 0
    photos = db.query(Photo).filter(Photo.event_id == event_id).all()
    for photo in photos:
        if not photo.original_path or not Path(photo.original_path).exists():
            continue
        photo.status = "QUEUED"
        photo.error = ""
        photo.published = False
        db.add(Job(event_id=event.id, photo_id=photo.id, type="PROCESS_PHOTO", priority=15))
        count += 1
    db.commit()
    return {"ok": True, "queued": count}


@router.get("/{event_id}/failed-jobs")
def failed_jobs(event_id: str, db: Session = Depends(get_db)):
    rows = db.query(Job).filter(Job.event_id == event_id, Job.state == "FAILED").order_by(Job.updated_at.desc()).limit(200).all()
    return [
        {
            "id": job.id,
            "photo_id": job.photo_id,
            "type": job.type,
            "stage": job.type.replace("_", " ").title(),
            "error": job.error,
            "attempts": job.attempts,
            "timestamp": job.updated_at.isoformat(),
        }
        for job in rows
    ]


@router.post("/{event_id}/failed-jobs/{job_id}/retry")
def retry_failed_job(event_id: str, job_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job or job.event_id != event_id:
        raise HTTPException(404, "Job not found")
    job.state = "RETRYING"
    job.error = ""
    job.attempts = 0
    job.available_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.post("/{event_id}/failed-jobs/retry-all")
def retry_all_failed_jobs(event_id: str, db: Session = Depends(get_db)):
    count = 0
    for job in db.query(Job).filter(Job.event_id == event_id, Job.state == "FAILED").all():
        job.state = "RETRYING"
        job.error = ""
        job.attempts = 0
        job.available_at = datetime.utcnow()
        count += 1
    db.commit()
    return {"ok": True, "count": count}


@router.get("/{event_id}/qr.png")
def qr_png(event_id: str, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    path = make_qr(db, event)
    return FileResponse(path, media_type="image/png")


def make_qr(db: Session, event: Event) -> Path:
    path = Path(event.root_path) / "CACHE" / "gallery_qr.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    img = qrcode.make(gallery_url(db, event.public_id))
    img.save(path)
    return path
