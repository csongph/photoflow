from __future__ import annotations

import json
import hashlib
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
    pin = str(gallery_settings.pop("optional_pin", "") or "").strip()
    gallery_settings["pin_hash"] = hashlib.sha256(pin.encode("utf-8")).hexdigest() if pin else ""
    return {
        "public_id": event.public_id,
        "name": event.name,
        "event_date": event.event_date,
        "description": event.description,
        "gallery_settings": gallery_settings,
    }


def photo_payload(event: Event, photo: Photo) -> dict[str, Any]:
    filename = Path(photo.finished_path).name if photo.finished_path else ""
    filename = filename or photo.filename or f"{photo.id}.jpg"
    capture_id = (photo.capture_id or photo.id or filename).strip()
    storage_provider = (photo.storage_provider or "local").strip()
    storage_object_id = (photo.storage_object_id or "").strip()
    variants = []
    for kind, object_id in (
        ("finished", storage_object_id),
        ("preview", (photo.preview_object_id or "").strip()),
        ("thumbnail", (photo.thumbnail_object_id or "").strip()),
    ):
        if object_id:
            variants.append({
                "kind": kind,
                "storage_provider": storage_provider,
                "storage_object_id": object_id,
                "width": 0,
                "height": 0,
            })
    return {
        "public_id": event.public_id,
        "local_photo_id": photo.id,
        "filename": filename[:260],
        "capture_id": capture_id[:220],
        "storage_provider": storage_provider[:60],
        "storage_object_id": storage_object_id[:300],
        "published": bool(photo.published),
        "hidden": bool(photo.hidden),
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


def list_cloud_events(*, strict: bool = False) -> list[dict[str, Any]]:
    base = cloud_api_url()
    if not base:
        if strict:
            raise CloudSyncError("Cloud API is not configured")
        return []
    try:
        headers = sync_headers()
        result: list[dict[str, Any]] = []
        with httpx.Client(timeout=30) as client:
            offset = 0
            while True:
                response = client.get(f"{base}/api/sync/events", params={"offset": offset, "limit": 100}, headers=headers)
                response.raise_for_status()
                events = response.json()
                if not isinstance(events, list):
                    raise ValueError("Cloud returned an invalid event list")
                for event in events:
                    if not isinstance(event, dict):
                        raise ValueError("Cloud returned an invalid event")
                    event["photos"] = []
                    photo_offset = 0
                    while True:
                        photos_response = client.get(
                            f"{base}/api/sync/events/{event['public_id']}/photos",
                            params={"offset": photo_offset, "limit": 200},
                            headers=headers,
                        )
                        photos_response.raise_for_status()
                        photos = photos_response.json()
                        if not isinstance(photos, list):
                            raise ValueError("Cloud returned an invalid photo list")
                        event["photos"].extend(photos)
                        photo_offset += len(photos)
                        if len(photos) < 200:
                            break
                    result.append(event)
                offset += len(events)
                if len(events) < 100:
                    break
        return result
    except Exception as exc:
        log.warning("Could not load cloud events: %s", exc)
        if strict:
            raise CloudSyncError(f"Cloud event listing failed: {exc}") from exc
        return []


def fetch_cloud_events(*, strict: bool = False) -> list[dict[str, Any]]:
    """Read cloud events with the private sync token (legacy alias)."""
    return list_cloud_events(strict=strict)
