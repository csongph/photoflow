from __future__ import annotations

from pydantic import BaseModel, Field


class GallerySettings(BaseModel):
    enable_gallery: bool = True
    allow_download: bool = True
    find_my_photos: bool = True
    instant_publish: bool = True
    review_before_publish: bool = False
    optional_pin: str = ""
    credit_text: str = "ถ่ายภาพโดยทีมโสตโรงเรียน"
    report_contact: str = ""


class DriveSettings(BaseModel):
    upload_finished_photos: bool = False
    upload_originals: bool = False


class EventCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    description: str = ""
    event_date: str = ""
    gallery: GallerySettings = Field(default_factory=GallerySettings)
    drive: DriveSettings = Field(default_factory=DriveSettings)


class EventOut(BaseModel):
    id: str
    public_id: str
    name: str
    status: str
    root_path: str
    incoming_path: str
    gallery_url: str
