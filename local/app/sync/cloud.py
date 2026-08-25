from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

from ..config import settings
from ..database import SessionLocal
from ..models import Event, Photo, Setting

log = logging.getLogger("photoflow")


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
        "filename": photo.filename,
        "capture_id": photo.capture_id,
        "storage_provider": photo.storage_provider,
        "storage_object_id": photo.storage_object_id,
        "published": photo.published,
        "hidden": photo.hidden,
        "variants": variants,
    }


def post(path: str, payload: dict[str, Any]) -> None:
    base = cloud_api_url()
    if not base:
        return
    with httpx.Client(timeout=20) as client:
        try:
            response = client.post(f"{base}{path}", json=payload, headers=sync_headers())
            response.raise_for_status()
        except Exception as exc:
            log.warning("Cloud sync failed for %s: %s", path, exc)


def sync_event(event: Event) -> None:
    post("/api/sync/event", event_payload(event))


def sync_photo(event: Event, photo: Photo) -> None:
    sync_event(event)
    post("/api/sync/photo", photo_payload(event, photo))
