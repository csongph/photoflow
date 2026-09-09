from __future__ import annotations

import os
import secrets
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Job, Setting, Upload
from ..uploader.storage import AUTH_URL, DRIVE_SCOPE, TOKEN_URL

router = APIRouter(prefix="/api/google", tags=["google-drive"])


def get_setting(db: Session, key: str, default: str = "") -> str:
    row = db.get(Setting, key)
    return row.value if row else default


def set_setting(db: Session, key: str, value: str) -> None:
    db.merge(Setting(key=key, value=value))


def google_configured() -> bool:
    return bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET") and os.getenv("GOOGLE_REDIRECT_URI"))


@router.get("/status")
def status(db: Session = Depends(get_db)):
    refresh_token = get_setting(db, "google_refresh_token")
    ready = db.query(Upload).filter(Upload.state.in_(["READY_TO_UPLOAD", "QUEUED"])).count()
    uploaded = db.query(Upload).filter(Upload.state == "UPLOADED").count()
    return {
        "configured": google_configured(),
        "connected": bool(refresh_token),
        "root_folder": get_setting(db, "drive_root", "MomentLink Events"),
        "ready_to_upload": ready,
        "uploaded": uploaded,
        "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI", ""),
        "needs_reconnect": not bool(refresh_token) and ready > 0,
    }


@router.get("/connect")
def connect(db: Session = Depends(get_db)):
    if not google_configured():
        raise HTTPException(400, "ตั้งค่า GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET และ GOOGLE_REDIRECT_URI ใน .env ก่อน")
    state = secrets.token_urlsafe(24)
    set_setting(db, "google_oauth_state", state)
    db.commit()
    params = {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI"),
        "response_type": "code",
        "scope": DRIVE_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return RedirectResponse(f"{AUTH_URL}?{urlencode(params)}")


@router.get("/callback")
def callback(code: str = "", state: str = "", error: str = "", db: Session = Depends(get_db)):
    if error:
        raise HTTPException(400, f"Google OAuth error: {error}")
    expected_state = get_setting(db, "google_oauth_state")
    if not state or state != expected_state:
        raise HTTPException(400, "OAuth state ไม่ถูกต้อง")
    with httpx.Client(timeout=30) as client:
        response = client.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI"),
                "grant_type": "authorization_code",
            },
        )
    if response.status_code >= 400:
        raise HTTPException(400, f"แลก token ไม่สำเร็จ: {response.text[:500]}")
    body = response.json()
    refresh_token = body.get("refresh_token")
    if not refresh_token:
        raise HTTPException(400, "Google ไม่ส่ง refresh_token กลับมา ให้ disconnect/reconnect และเลือก consent ใหม่")
    set_setting(db, "google_refresh_token", refresh_token)
    set_setting(db, "google_connected_at", datetime.utcnow().isoformat() + "Z")
    set_setting(db, "google_oauth_state", "")
    db.commit()
    return HTMLResponse("<h1>เชื่อมต่อ Google Drive สำเร็จ</h1><p>กลับไปหน้า Settings แล้วกด Retry Uploads เพื่อนำรูปที่ค้างกลับเข้าคิว</p><p><a href='/settings'>เปิด Settings</a></p>")


@router.post("/disconnect")
def disconnect(db: Session = Depends(get_db)):
    set_setting(db, "google_refresh_token", "")
    set_setting(db, "google_connected_at", "")
    db.commit()
    return {"ok": True}


@router.post("/retry-ready")
def retry_ready_uploads(db: Session = Depends(get_db)):
    count = 0
    uploads = db.query(Upload).filter(Upload.state.in_(["READY_TO_UPLOAD", "QUEUED"])).all()
    for upload in uploads:
        upload.state = "QUEUED"
        upload.error = ""
        db.add(Job(event_id=upload.event_id, photo_id=upload.photo_id, type="UPLOAD_VARIANT", priority=25, payload_json=f'{{"upload_id":"{upload.id}"}}'))
        count += 1
    db.commit()
    return {"ok": True, "queued": count}
