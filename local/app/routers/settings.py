from __future__ import annotations

import subprocess
import string
from os import PathLike
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Setting
from ..config import settings
from ..utils.local_paths import ensure_event_root, event_root_path
from ..utils.public_url import public_gallery_base_url

router = APIRouter(prefix="/api/settings", tags=["settings"])


def writable_event_root(path: str | PathLike[str], db: Session) -> Path:
    raw = str(path).strip()
    if not raw:
        raise HTTPException(400, "Event Root is required")
    event_root = Path(raw).expanduser()
    try:
        event_root.mkdir(parents=True, exist_ok=True)
        probe = event_root / ".momentlink_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as exc:
        raise HTTPException(400, f"Folder is not writable: {exc}")

    db.merge(Setting(key="event_root", value=str(event_root)))
    db.commit()
    return event_root


def folder_writable(path: Path) -> bool:
    if not path.exists() or not path.is_dir():
        return False
    try:
        probe = path / ".momentlink_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def folder_option(label: str, path: Path, recommended: bool = False) -> dict:
    parent = path if path.exists() else path.parent
    writable = folder_writable(path) if path.exists() else folder_writable(parent)
    return {
        "label": label,
        "path": str(path),
        "exists": path.exists(),
        "writable": writable,
        "recommended": recommended,
    }


def drive_roots() -> list[Path]:
    roots: list[Path] = []
    for letter in string.ascii_uppercase:
        path = Path(f"{letter}:\\")
        if path.exists():
            roots.append(path)
    return roots


def folder_row(path: Path) -> dict:
    writable = folder_writable(path)
    return {
        "name": path.name or str(path),
        "path": str(path),
        "exists": path.exists(),
        "writable": writable,
        "can_create_child": writable,
    }


@router.get("")
def get_settings(db: Session = Depends(get_db)):
    values = {
        "event_root": str(event_root_path(db)),
        "cloud_api_url": settings.cloud_api_url,
        "public_gallery_base_url": public_gallery_base_url(db),
        "worker_count": str(settings.max_workers),
        "jpeg_quality": str(settings.jpeg_quality),
        "default_profile": "Balanced",
    }
    secret_keys = {"google_refresh_token", "google_oauth_state"}
    values.update({row.key: row.value for row in db.query(Setting).all() if row.key not in secret_keys})
    return values


@router.get("/event-root-options")
def event_root_options(db: Session = Depends(get_db)):
    home = Path.home()
    options = [
        folder_option("Current setting", event_root_path(db), True),
        folder_option("Documents / MomentLink Events", home / "Documents" / "MomentLink Events", True),
        folder_option("Pictures / MomentLink Events", home / "Pictures" / "MomentLink Events"),
        folder_option("Desktop / MomentLink Events", home / "Desktop" / "MomentLink Events"),
        folder_option("Project local events", settings.event_root),
    ]
    for drive in ["D:\\", "E:\\"]:
        root = Path(drive)
        if root.exists() and folder_writable(root):
            options.append(folder_option(f"{drive}MomentLink Events", root / "MomentLink Events"))
    seen: set[str] = set()
    unique = []
    for option in options:
        key = option["path"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(option)
    return {"options": unique}


@router.get("/local-folders")
def local_folders(path: str = Query("", max_length=1000)):
    if not path.strip():
        home = Path.home()
        roots = drive_roots()
        quick = [home, home / "Documents", home / "Pictures", home / "Desktop"]
        folders = []
        seen: set[str] = set()
        for item in [*roots, *quick]:
            key = str(item).lower()
            if key in seen:
                continue
            seen.add(key)
            folders.append(folder_row(item))
        return {
            "current": "",
            "parent": "",
            "writable": False,
            "can_create_child": False,
            "folders": folders,
        }

    current = Path(path).expanduser()
    try:
        current = current.resolve()
    except OSError as exc:
        raise HTTPException(400, f"Cannot open folder: {exc}")
    if not current.exists():
        raise HTTPException(404, "Folder not found")
    if not current.is_dir():
        raise HTTPException(400, "Path is not a folder")

    folders = []
    try:
        children = sorted(
            [child for child in current.iterdir() if child.is_dir()],
            key=lambda item: item.name.lower(),
        )
    except OSError as exc:
        raise HTTPException(400, f"Cannot read folder: {exc}")
    for child in children[:250]:
        folders.append(folder_row(child))

    parent = "" if current.parent == current else str(current.parent)
    return {
        "current": str(current),
        "parent": parent,
        "writable": folder_writable(current),
        "can_create_child": folder_writable(current),
        "folders": folders,
    }


@router.post("/local-folders")
def create_local_folder(payload: dict[str, str]):
    parent_raw = (payload.get("parent") or "").strip()
    name_raw = (payload.get("name") or "").strip()
    if not parent_raw or not name_raw:
        raise HTTPException(400, "Parent and folder name are required")
    if any(sep in name_raw for sep in ["\\", "/", ":"]):
        raise HTTPException(400, "Folder name cannot contain path separators")
    parent = Path(parent_raw).expanduser().resolve()
    if not parent.exists() or not parent.is_dir():
        raise HTTPException(404, "Parent folder not found")
    path = parent / name_raw
    try:
        path.mkdir(parents=False, exist_ok=True)
    except OSError as exc:
        raise HTTPException(400, f"Cannot create folder: {exc}")
    return {"ok": True, "path": str(path)}


@router.post("")
def save_settings(payload: dict[str, str], db: Session = Depends(get_db)):
    for key, value in payload.items():
        if len(key) > 120:
            continue
        db.merge(Setting(key=key, value=str(value)))
    db.commit()
    if "event_root" in payload:
        ensure_event_root(db)
    return {"ok": True}


@router.post("/verify-event-root")
def verify_event_root(payload: dict[str, str], db: Session = Depends(get_db)):
    path = writable_event_root(payload.get("event_root") or str(event_root_path(db)), db)
    return {"ok": True, "event_root": str(path)}


@router.post("/choose-event-root")
def choose_event_root(db: Session = Depends(get_db)):
    selected = ""
    try:
        script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog; "
            "$dialog.Description = 'เลือกโฟลเดอร์เก็บงาน MomentLink'; "
            "$dialog.ShowNewFolderButton = $true; "
            "if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { "
            "  [Console]::Out.Write($dialog.SelectedPath) "
            "}"
        )
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-STA", "-Command", script],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        if completed.returncode == 0:
            selected = completed.stdout.strip()
    except Exception:
        selected = ""

    if not selected:
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            selected = filedialog.askdirectory(title="เลือกโฟลเดอร์เก็บงาน MomentLink")
            root.destroy()
        except Exception as exc:
            raise HTTPException(500, f"Could not open folder picker: {exc}")

    if not selected:
        return {"ok": False, "cancelled": True, "event_root": str(event_root_path(db))}

    path = writable_event_root(selected, db)
    return {"ok": True, "event_root": str(path)}
