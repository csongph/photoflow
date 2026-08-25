from __future__ import annotations

import importlib.util
import os
import socket
import shutil
import sys
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Event, Job, Photo, Setting, Upload
from ..utils.local_paths import ensure_event_root
from ..utils.public_url import public_gallery_base_url
from ..watcher.service import watcher_manager

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])

REQUIRED_PACKAGES = ["fastapi", "uvicorn", "sqlalchemy", "watchdog", "PIL", "qrcode"]
OPTIONAL_PACKAGES = {
    "cv2": "optional: needed only for offline face search",
    "rawpy": "optional: needed only when importing RAW camera files",
}


def check(status: str, message: str, required: bool = True) -> dict:
    return {"status": status, "message": message, "required": required}


def package_status(name: str, required: bool, optional_message: str = "optional package") -> dict:
    found = importlib.util.find_spec(name) is not None
    if found:
        return check("OK", "installed", required)
    if required:
        return check("FAIL", "not installed", required)
    return check("OPTIONAL", optional_message, False)


def can_write(path: Path) -> bool:
    path.mkdir(parents=True, exist_ok=True)
    probe = path / ".photoflow_write_test"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink(missing_ok=True)
    return True


def local_lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return ""


def write_check(path: Path) -> tuple[bool, str]:
    try:
        can_write(path)
        return True, f"writable: {path}"
    except OSError as exc:
        return False, str(exc)


@router.get("")
def diagnostics(db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.status == "LIVE").order_by(Event.updated_at.desc()).first()
    rows: dict[str, dict] = {}
    event_root = ensure_event_root(db)

    rows["python"] = check(
        "OK" if sys.version_info >= (3, 11) else "FAIL",
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        True,
    )
    for path_name, path in {
        "data_dir": settings.data_dir,
        "logs_dir": settings.logs_dir,
        "event_root": event_root,
    }.items():
        try:
            rows[path_name] = check("OK", f"writable: {path}", True) if can_write(path) else check("FAIL", f"not writable: {path}", True)
        except OSError as exc:
            rows[path_name] = check("FAIL", str(exc), True)

    try:
        db.execute(text("select 1"))
        rows["sqlite"] = check("OK", "database reachable", True)
    except Exception as exc:
        rows["sqlite"] = check("FAIL", str(exc), True)

    disk = shutil.disk_usage(event_root)
    rows["disk"] = check("OK" if disk.free > 2 * 1024 * 1024 * 1024 else "WARN", f"{round(disk.free / 1024 / 1024 / 1024, 1)} GB free", True)

    for package in REQUIRED_PACKAGES:
        rows[f"package_{package}"] = package_status(package, True)
    for package, message in OPTIONAL_PACKAGES.items():
        rows[f"package_{package}"] = package_status(package, False, message)

    try:
        internet_response = httpx.get("https://www.googleapis.com/generate_204", timeout=3)
        rows["internet"] = check("OK" if internet_response.status_code in {204, 200} else "WARN", f"HTTP {internet_response.status_code}", False)
    except Exception as exc:
        rows["internet"] = check("WARN", f"offline or blocked: {exc}", False)
    if settings.cloud_api_url:
        try:
            cloud_response = httpx.get(f"{settings.cloud_api_url.rstrip('/')}/healthz", timeout=3)
            rows["cloud_api"] = check("OK" if cloud_response.status_code == 200 else "WARN", f"HTTP {cloud_response.status_code}: {settings.cloud_api_url}", False)
        except Exception as exc:
            rows["cloud_api"] = check("WARN", f"unreachable: {exc}", False)
    else:
        rows["cloud_api"] = check("OPTIONAL", "not configured: local mode can run without cloud API", False)
    google_connected = bool(db.get(Setting, "google_refresh_token") and db.get(Setting, "google_refresh_token").value)
    google_configured = bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"))
    rows["google_drive"] = check(
        "OK" if google_connected else ("WARN" if google_configured else "OPTIONAL"),
        "CONNECTED" if google_connected else ("credentials configured, connect required" if google_configured else "NEEDS MANUAL CREDENTIAL"),
        False,
    )
    rows["face_engine"] = check("OK" if importlib.util.find_spec("cv2") else "OPTIONAL", "OpenCV available" if importlib.util.find_spec("cv2") else "offline face engine unavailable", False)
    rows["watcher"] = check("OK" if event and event.id in watcher_manager.observers else "OPTIONAL", "watching active event" if event and event.id in watcher_manager.observers else "idle: start an event to watch INCOMING", False)
    rows["local_server"] = check("OK", f"{settings.local_host}:{settings.local_port}", True)

    queues = {
        "processing": db.query(Job).filter(Job.type == "PROCESS_PHOTO", Job.state.in_(["QUEUED", "RETRYING", "PROCESSING"])).count(),
        "upload": db.query(Job).filter(Job.type == "UPLOAD_VARIANT", Job.state.in_(["QUEUED", "RETRYING", "PROCESSING"])).count(),
        "face": db.query(Job).filter(Job.type == "FACE_INDEX", Job.state.in_(["QUEUED", "RETRYING", "PROCESSING"])).count(),
        "failed": db.query(Job).filter(Job.state == "FAILED").count(),
        "uploads_ready": db.query(Upload).filter(Upload.state.in_(["QUEUED", "READY_TO_UPLOAD"])).count(),
    }
    database = {
        "events": db.query(Event).count(),
        "photos": db.query(Photo).count(),
        "jobs": db.query(Job).count(),
        "uploads": db.query(Upload).count(),
        "uploads_uploaded": db.query(Upload).filter(Upload.state == "UPLOADED").count(),
        "uploads_ready": db.query(Upload).filter(Upload.state.in_(["QUEUED", "READY_TO_UPLOAD"])).count(),
        "uploads_failed": db.query(Upload).filter(Upload.state == "FAILED").count(),
    }
    return {"checks": rows, "queues": queues, "database": database}


@router.get("/readiness")
def readiness(db: Session = Depends(get_db)):
    event_root = ensure_event_root(db)
    event_root_ok, event_root_message = write_check(event_root)
    lan_ip = local_lan_ip()
    public_base = public_gallery_base_url(db)
    public_ok = bool(lan_ip and lan_ip in public_base and "127.0.0.1" not in public_base and "localhost" not in public_base)
    google_connected = bool(db.get(Setting, "google_refresh_token") and db.get(Setting, "google_refresh_token").value)
    google_configured = bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET") and os.getenv("GOOGLE_REDIRECT_URI"))
    active_event = db.query(Event).filter(Event.status == "LIVE").order_by(Event.updated_at.desc()).first()
    latest_event = active_event or db.query(Event).order_by(Event.updated_at.desc()).first()
    event_preflight = None
    if latest_event:
        incoming = Path(latest_event.incoming_path)
        incoming_ok, incoming_message = write_check(incoming) if incoming.exists() else (False, f"missing: {incoming}")
        event_preflight = {
            "event_id": latest_event.id,
            "event_name": latest_event.name,
            "status": latest_event.status,
            "incoming_ok": incoming_ok,
            "incoming_message": incoming_message,
            "gallery_url": f"{public_base}/{latest_event.public_id}",
        }

    steps = [
        {"key": "event_root", "label": "Event Root", "ok": event_root_ok, "required": True, "message": event_root_message, "fix_url": "/settings"},
        {"key": "public_gallery_url", "label": "Public Gallery URL / QR", "ok": public_ok, "required": True, "message": public_base if public_ok else f"ตั้งเป็น URL ที่มือถือเปิดได้ เช่น http://{lan_ip}:8000/gallery สำหรับทดสอบ LAN หรือ https://your-domain.com/gallery หลังดีพรอย", "fix_url": "/settings"},
        {"key": "google_drive", "label": "Google Drive", "ok": google_connected, "required": False, "message": "connected" if google_connected else ("configured, connect required" if google_configured else "optional: not configured"), "fix_url": "/settings"},
        {"key": "database", "label": "Database", "ok": True, "required": True, "message": f"{db.query(Event).count()} event(s), {db.query(Photo).count()} photo(s)", "fix_url": "/diagnostics"},
    ]
    if event_preflight:
        steps.append({"key": "incoming", "label": "Latest Event INCOMING", "ok": event_preflight["incoming_ok"], "required": True, "message": event_preflight["incoming_message"], "fix_url": "/events"})
    required_failed = [step for step in steps if step["required"] and not step["ok"]]
    return {
        "ok": not required_failed,
        "lan_ip": lan_ip,
        "public_gallery_base_url": public_base,
        "event_root": str(event_root),
        "active_event": event_preflight,
        "steps": steps,
        "failed_required": required_failed,
    }


@router.post("/system-test")
def system_test(db: Session = Depends(get_db)):
    result = diagnostics(db)
    failed_required = [name for name, row in result["checks"].items() if row["required"] and row["status"] == "FAIL"]
    return {"ok": not failed_required, "failed_required": failed_required, **result}
