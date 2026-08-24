from __future__ import annotations

import shutil
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Event, Job, Photo, Setting, Upload
from ..utils.local_paths import ensure_event_root
from ..utils.public_url import public_gallery_url

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.status == "LIVE").order_by(Event.updated_at.desc()).first()
    if not event:
        event = db.query(Event).order_by(Event.created_at.desc()).first()
    if not event:
        return {"active_event": None, "counts": {}, "latest_photos": [], "health": health(db, None), "queues": {}}
    counts = {
        "captured": db.query(Photo).filter(Photo.event_id == event.id).count(),
        "processed": db.query(Photo).filter(Photo.event_id == event.id, Photo.finished_path != "").count(),
        "uploaded": db.query(Upload).filter(Upload.event_id == event.id, Upload.state == "UPLOADED").count(),
        "published": db.query(Photo).filter(Photo.event_id == event.id, Photo.published == True).count(),
        "review": db.query(Photo).filter(Photo.event_id == event.id, Photo.status == "AWAITING_REVIEW").count(),
        "queue": db.query(Job).filter(Job.event_id == event.id, Job.state.in_(["QUEUED", "RETRYING", "PROCESSING"])).count(),
        "failed": db.query(Job).filter(Job.event_id == event.id, Job.state == "FAILED").count(),
    }
    latest = db.query(Photo).filter(Photo.event_id == event.id).order_by(Photo.created_at.desc()).limit(8).all()
    return {
        "active_event": {
            "id": event.id,
            "name": event.name,
            "status": event.status,
            "incoming_path": event.incoming_path,
            "gallery_url": public_gallery_url(db, event.public_id),
            "publishing_paused": event.publishing_paused,
        },
        "counts": counts,
        "latest_photos": [
            {
                "id": p.id,
                "filename": p.filename,
                "status": p.status,
                "published": p.published,
                "hidden": p.hidden,
                "thumb": f"/media/{p.event_id}/THUMBNAILS/{Path(p.thumbnail_path).name}" if p.thumbnail_path else "",
            }
            for p in latest
        ],
        "health": health(db, event),
        "queues": {
            "processing": db.query(Job).filter(Job.event_id == event.id, Job.type == "PROCESS_PHOTO", Job.state.in_(["QUEUED", "RETRYING", "PROCESSING"])).count(),
            "upload": db.query(Job).filter(Job.event_id == event.id, Job.type == "UPLOAD_VARIANT", Job.state.in_(["QUEUED", "RETRYING", "PROCESSING"])).count(),
            "face": db.query(Job).filter(Job.event_id == event.id, Job.type == "FACE_INDEX", Job.state.in_(["QUEUED", "RETRYING"])).count(),
        },
    }


def health(db: Session, event: Event | None):
    root = ensure_event_root(db)
    disk = shutil.disk_usage(root)
    refresh_token = db.get(Setting, "google_refresh_token")
    connected_drive = bool(refresh_token and refresh_token.value)
    queued_uploads = db.query(Upload).filter(Upload.state.in_(["READY_TO_UPLOAD", "QUEUED"])).count()
    try:
        response = httpx.get("https://www.googleapis.com/generate_204", timeout=2)
        internet = "Online" if response.status_code in {204, 200} else "Limited"
    except Exception:
        internet = "Offline"
    return {
        "folder": "Watching" if event and event.status == "LIVE" else "Idle",
        "internet": internet,
        "cloud": "Not configured" if not settings.cloud_api_url else "Configured",
        "drive": "Connected" if connected_drive else "Not connected",
        "drive_pending_uploads": queued_uploads,
        "disk_free_gb": round(disk.free / 1024 / 1024 / 1024, 1),
    }
