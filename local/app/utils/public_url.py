from __future__ import annotations

from sqlalchemy.orm import Session

from ..config import settings
from ..models import Setting


def public_gallery_base_url(db: Session) -> str:
    row = db.get(Setting, "public_gallery_base_url")
    value = row.value if row and row.value else settings.public_gallery_base_url
    return value.rstrip("/")


def public_gallery_url(db: Session, public_id: str) -> str:
    return f"{public_gallery_base_url(db)}/{public_id}"
