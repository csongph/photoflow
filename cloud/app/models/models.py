from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


def new_id() -> str:
    return uuid.uuid4().hex


class Event(Base):
    __tablename__ = "events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    public_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180))
    event_date: Mapped[str] = mapped_column(String(20), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    pin_hash: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Photo(Base):
    __tablename__ = "photos"
    __table_args__ = (UniqueConstraint("event_id", "local_photo_id", name="uq_photo_event_local"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), index=True)
    local_photo_id: Mapped[str] = mapped_column(String(64), index=True)
    filename: Mapped[str] = mapped_column(String(260))
    capture_id: Mapped[str] = mapped_column(String(220), index=True)
    storage_provider: Mapped[str] = mapped_column(String(60))
    storage_object_id: Mapped[str] = mapped_column(String(300), default="")
    published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PhotoVariant(Base):
    __tablename__ = "photo_variants"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    photo_id: Mapped[str] = mapped_column(ForeignKey("photos.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    storage_provider: Mapped[str] = mapped_column(String(60))
    storage_object_id: Mapped[str] = mapped_column(String(300))
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)


class GallerySettings(Base):
    __tablename__ = "gallery_settings"
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), primary_key=True)
    allow_download: Mapped[bool] = mapped_column(Boolean, default=True)
    find_my_photos: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_refresh: Mapped[bool] = mapped_column(Boolean, default=True)


class SyncJob(Base):
    __tablename__ = "sync_jobs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), index=True)
    state: Mapped[str] = mapped_column(String(40), index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PhotoFace(Base):
    __tablename__ = "photo_faces"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), index=True)
    photo_id: Mapped[str] = mapped_column(ForeignKey("photos.id"), index=True)
    embedding: Mapped[bytes] = mapped_column(LargeBinary)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    bounding_box: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FaceSearchSession(Base):
    __tablename__ = "face_search_sessions"
    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="CREATED")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

Index("ix_photo_faces_event_photo", PhotoFace.event_id, PhotoFace.photo_id)

