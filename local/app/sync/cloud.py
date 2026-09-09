from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx

from ..config import settings
from ..database import SessionLocal
from ..models import Event, Photo, Setting

log = logging.getLogger("photoflow")


class CloudSyncError(RuntimeError):
    pass


def cloud_api_url() -> str:
    configured = (os.getenv("CLOUD_API_URL", "") or settings.cloud_api_url).strip()
    if configured:
        return configured.rstrip("/")
    try:
        with SessionLocal() as db:
            row = db.get(Setting, "cloud_api_url")
            return (row.value if row and row.value else "").strip().rstrip("/")
    except Exception:
        return ""


def sync_headers() -> dict[str, str]:
    token = os.getenv("CLOUD_SYNC_TOKEN", "").strip()
    return {"Authorization": f"Bearer {token}"} if token else {}


def enabled() -> bool:
    return bool(cloud_api_url())


def event_payload(event: Event) -> dict[str, Any]:
    try:
        gallery_settings = json.loads(event.gallery_json or "{}")
    except json.JSONDecodeError:
        gallery_settings = {}
    return {
        "public_id": event.public_id,
        "name": event.name,
        "event_date": event.event_date,
        "description": event.description,
        "gallery_settings": gallery_settings,
    }


def photo_payload(event: Event, photo: Photo) -> dict[str, Any]:
    variants = []
    if photo.storage_object_id:
        variants.append({
            "kind": "finished",
            "storage_provider": photo.storage_provider or "google_drive",
            "storage_object_id": photo.storage_object_id,
            "width": 0,
            "height": 0,
        })
    return {
        "public_id": event.public_id,
        "local_photo_id": photo.id,
        "filename": Path(photo.finished_path).name if photo.finished_path else photo.filename,
        "capture_id": photo.capture_id,
        "storage_provider": photo.storage_provider,
        "storage_object_id": photo.storage_object_id,
        "published": photo.published,
        "hidden": photo.hidden,
        "variants": variants,
    }


def post(path: str, payload: dict[str, Any], *, strict: bool = False) -> bool:
    base = cloud_api_url()
    if not base:
        if strict:
            raise CloudSyncError("Cloud API is not configured")
        return False
    with httpx.Client(timeout=20) as client:
        try:
            response = client.post(f"{base}{path}", json=payload, headers=sync_headers())
            response.raise_for_status()
            return True
        except Exception as exc:
            log.warning("Cloud sync failed for %s: %s", path, exc)
            if strict:
                raise CloudSyncError(f"Cloud sync failed for {path}: {exc}") from exc
            return False


def delete(path: str, *, strict: bool = False) -> bool:
    base = cloud_api_url()
    if not base:
        if strict:
            raise CloudSyncError("Cloud API is not configured")
        return False
    with httpx.Client(timeout=20) as client:
        try:
            response = client.delete(f"{base}{path}", headers=sync_headers())
            response.raise_for_status()
            return True
        except Exception as exc:
            log.warning("Cloud delete failed for %s: %s", path, exc)
            if strict:
                raise CloudSyncError(f"Cloud delete failed for {path}: {exc}") from exc
            return False


def sync_event(event: Event, *, strict: bool = False) -> bool:
    return post("/api/sync/event", event_payload(event), strict=strict)


def sync_photo(event: Event, photo: Photo, *, strict: bool = False) -> bool:
    event_ok = sync_event(event, strict=strict)
    photo_ok = post("/api/sync/photo", photo_payload(event, photo), strict=strict)
    return event_ok and photo_ok


def delete_cloud_event(public_id: str, *, strict: bool = False) -> bool:
    return delete(f"/api/sync/event/{public_id}", strict=strict)
