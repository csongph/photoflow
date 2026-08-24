from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from ..config import settings
from ..models import Setting


def event_root_path(db: Session) -> Path:
    row = db.get(Setting, "event_root")
    value = row.value.strip() if row and row.value else ""
    return Path(value) if value else settings.event_root


def ensure_event_root(db: Session) -> Path:
    path = event_root_path(db)
    path.mkdir(parents=True, exist_ok=True)
    return path
