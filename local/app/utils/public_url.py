from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.orm import Session

from ..config import settings
from ..models import Setting


def public_gallery_base_url(db: Session) -> str:
    if settings.cloud_api_url and settings.public_gallery_base_url:
        return settings.public_gallery_base_url.rstrip("/")
    row = db.get(Setting, "public_gallery_base_url")
    value = row.value if row and row.value else settings.public_gallery_base_url
    return value.rstrip("/")


def public_gallery_url(db: Session, public_id: str) -> str:
    base = public_gallery_base_url(db)
    if base.startswith(("http://", "https://")):
        parts = urlsplit(base)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query["event"] = public_id
        return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", urlencode(query), parts.fragment))
    return f"{base}/{public_id}"
