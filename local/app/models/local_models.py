from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


def new_id() -> str:
    return uuid.uuid4().hex


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Event(Base, TimestampMixin):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    public_id: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    event_date: Mapped[str] = mapped_column(String(20), default="")
    slug: Mapped[str] = mapped_column(String(220), index=True)
    status: Mapped[str] = mapped_column(String(32), default="CREATED", index=True)
    root_path: Mapped[str] = mapped_column(Text)
    incoming_path: Mapped[str] = mapped_column(Text)
    preset_id: Mapped[str] = mapped_column(String(80), default="neutral")
    processing_profile: Mapped[str] = mapped_column(String(32), default="Passthrough")
    auto_correction_json: Mapped[str] = mapped_column(Text, default="{}")
    gallery_json: Mapped[str] = mapped_column(Text, default="{}")
    drive_json: Mapped[str] = mapped_column(Text, default="{}")
    publishing_paused: Mapped[bool] = mapped_column(Boolean, default=False)

    photos: Mapped[list["Photo"]] = relationship(back_populates="event", cascade="all,delete")
    jobs: Mapped[list["Job"]] = relationship(back_populates="event", cascade="all,delete")


class Photo(Base, TimestampMixin):
    __tablename__ = "photos"
    __table_args__ = (
        UniqueConstraint("event_id", "checksum", name="uq_photo_event_checksum"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), index=True)
    capture_id: Mapped[str] = mapped_column(String(220), index=True)
    filename: Mapped[str] = mapped_column(String(260))
    original_path: Mapped[str] = mapped_column(Text, default="")
    working_path: Mapped[str] = mapped_column(Text, default="")
    finished_path: Mapped[str] = mapped_column(Text, default="")
    thumbnail_path: Mapped[str] = mapped_column(Text, default="")
    preview_path: Mapped[str] = mapped_column(Text, default="")
    checksum: Mapped[str] = mapped_column(String(64), index=True)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    mime_type: Mapped[str] = mapped_column(String(80), default="")
    raw_path: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="DETECTED", index=True)
    error: Mapped[str] = mapped_column(Text, default="")
    storage_provider: Mapped[str] = mapped_column(String(60), default="")
    storage_object_id: Mapped[str] = mapped_column(String(300), default="")
    thumbnail_object_id: Mapped[str] = mapped_column(String(300), default="")
    preview_object_id: Mapped[str] = mapped_column(String(300), default="")
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)

    event: Mapped[Event] = relationship(back_populates="photos")


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), index=True)
    photo_id: Mapped[str] = mapped_column(ForeignKey("photos.id"), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(40), index=True)
    state: Mapped[str] = mapped_column(String(40), default="QUEUED", index=True)
    priority: Mapped[int] = mapped_column(Integer, default=50, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str] = mapped_column(Text, default="")
    available_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    event: Mapped[Event] = relationship(back_populates="jobs")


class Preset(Base, TimestampMixin):
    __tablename__ = "presets"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="system")
    settings_json: Mapped[str] = mapped_column(Text)
    support_status: Mapped[str] = mapped_column(String(40), default="Fully Supported")
    warning: Mapped[str] = mapped_column(Text, default="")


class Upload(Base, TimestampMixin):
    __tablename__ = "uploads"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), index=True)
    photo_id: Mapped[str] = mapped_column(ForeignKey("photos.id"), index=True)
    variant: Mapped[str] = mapped_column(String(30))
    local_path: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(60), default="google_drive")
    object_id: Mapped[str] = mapped_column(String(300), default="")
    state: Mapped[str] = mapped_column(String(40), default="QUEUED", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")


class Setting(Base, TimestampMixin):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class SyncState(Base, TimestampMixin):
    __tablename__ = "sync_state"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
