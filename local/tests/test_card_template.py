from __future__ import annotations

import asyncio
import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi import HTTPException
from PIL import Image, ImageDraw
from starlette.datastructures import UploadFile

from local.app.database import Base, SessionLocal, engine, init_db
from local.app.models import Event, Job
from local.app.routers import events as events_router
from local.app.routers.events import default_photo_strip_slots, update_photo_strip_settings, upload_card_template, upload_photo_strip_layout


def _template_png(*, missing_slot: int | None = None) -> bytes:
    image = Image.new("RGBA", (600, 1800), (31, 22, 48, 255))
    draw = ImageDraw.Draw(image)
    if missing_slot is None:
        slots = range(4)
    else:
        slots = (index for index in range(4) if index != missing_slot)
    for index in slots:
        top = round((.16 + index * .19) * image.height)
        bottom = round((.16 + index * .19 + .165) * image.height)
        draw.rectangle((round(.12 * image.width), top, round(.88 * image.width), bottom), fill=(0, 0, 0, 0))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _canva_export_png() -> bytes:
    image = Image.new("RGBA", (600, 1800), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((14, 14, 586, 1786), radius=34, outline=(233, 134, 114, 255), width=5)
    draw.text((300, 135), "FESTIVAL", fill=(51, 40, 63, 255), anchor="mm")
    for index in range(4):
        top = round((.16 + index * .19) * image.height)
        draw.rounded_rectangle((72, top, 528, top + 297), radius=14, outline=(213, 179, 106, 255), width=5)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _photo_strip_png(count: int) -> bytes:
    image = Image.new("RGBA", (600, 1800), (31, 22, 48, 255))
    draw = ImageDraw.Draw(image)
    for slot in default_photo_strip_slots(count):
        x, y, width, height = (slot[key] for key in ("x", "y", "width", "height"))
        draw.rectangle((round(x * image.width), round(y * image.height), round((x + width) * image.width), round((y + height) * image.height)), fill=(0, 0, 0, 0))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _make_event(root: Path) -> Event:
    for name in ("INCOMING", "ORIGINAL", "FINISHED", "THUMBNAILS", "PREVIEWS", "CACHE"):
        (root / name).mkdir(parents=True, exist_ok=True)
    event = Event(
        public_id="card-template-test-event",
        name="Card Template Test",
        slug="card-template-test",
        root_path=str(root),
        incoming_path=str(root / "INCOMING"),
        gallery_json=json.dumps({"card_maker_enabled": True}),
    )
    return event


def _reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    init_db()


def test_admin_card_template_upload_saves_transparent_vertical_strip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _reset_db()
    monkeypatch.setattr(events_router, "cloud_sync_enabled", lambda: False)
    event = _make_event(tmp_path / "event")
    with SessionLocal() as db:
        db.add(event)
        db.commit()
        db.refresh(event)
        result = asyncio.run(upload_card_template(event.id, UploadFile(filename="festival-card.png", file=BytesIO(_template_png())), enabled=True, db=db))
        saved = db.get(Event, event.id)
        settings = json.loads(saved.gallery_json)
        assert result["ok"] is True
        assert result["filename"] == "festival-card.png"
        assert (Path(saved.root_path) / "CACHE" / "card-template.png").is_file()
        assert settings["card_maker_enabled"] is True
        assert settings["card_template_name"] == "festival-card.png"
        assert db.query(Job).filter_by(event_id=event.id, type="SYNC_CARD_TEMPLATE").count() == 0


def test_admin_card_template_rejects_missing_photo_slot_without_saving(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _reset_db()
    monkeypatch.setattr(events_router, "cloud_sync_enabled", lambda: False)
    event = _make_event(tmp_path / "event")
    with SessionLocal() as db:
        db.add(event)
        db.commit()
        db.refresh(event)
        upload = UploadFile(filename="broken-template.png", file=BytesIO(_template_png(missing_slot=2)))
        with pytest.raises(HTTPException) as error:
            asyncio.run(upload_card_template(event.id, upload, enabled=True, db=db))
        assert error.value.status_code == 422
        assert not (Path(event.root_path) / "CACHE" / "card-template.png").exists()


def test_admin_card_template_rejects_oversized_upload_before_decoding(tmp_path: Path):
    _reset_db()
    event = _make_event(tmp_path / "event")
    with SessionLocal() as db:
        db.add(event)
        db.commit()
        db.refresh(event)
        oversized = BytesIO(b"\x89PNG\r\n\x1a\n" + b"x" * (8 * 1024 * 1024 + 1))
        with pytest.raises(HTTPException) as error:
            asyncio.run(upload_card_template(event.id, UploadFile(filename="large.png", file=oversized), enabled=True, db=db))
        assert error.value.status_code == 413


def test_admin_card_template_normalizes_canva_white_export(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _reset_db()
    monkeypatch.setattr(events_router, "cloud_sync_enabled", lambda: False)
    event = _make_event(tmp_path / "event")
    with SessionLocal() as db:
        db.add(event)
        db.commit()
        db.refresh(event)
        result = asyncio.run(upload_card_template(
            event.id,
            UploadFile(filename="canva-export.png", file=BytesIO(_canva_export_png())),
            enabled=False,
            db=db,
        ))
        saved = Image.open(Path(event.root_path) / "CACHE" / "card-template.png").convert("RGBA")
        assert result["ok"] is True
        assert json.loads(db.get(Event, event.id).gallery_json)["card_maker_enabled"] is False
        assert saved.getpixel((300, 400))[3] == 0
        assert saved.getpixel((0, 0))[3] == 0
        assert saved.getpixel((16, 300))[3] > 0


def test_photo_strip_admin_must_upload_every_layout_before_enabling(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _reset_db()
    monkeypatch.setattr(events_router, "cloud_sync_enabled", lambda: False)
    event = _make_event(tmp_path / "event")
    with SessionLocal() as db:
        db.add(event)
        db.commit()
        db.refresh(event)
        theme = {"id": "festival", "name": "Festival", "description": "", "background_color": "#FFFFFF", "accent_color": "#E98672", "text_color": "#33283F", "caption": "", "layouts": {str(count): {"slots": default_photo_strip_slots(count)} for count in (2, 3, 4)}}
        update_photo_strip_settings(event.id, {"enabled": False, "active_theme_id": "festival", "themes": [theme]}, db)
        with pytest.raises(HTTPException) as error:
            update_photo_strip_settings(event.id, {"enabled": True, "active_theme_id": "festival", "themes": [theme]}, db)
        assert error.value.status_code == 422
        for count in (2, 3, 4):
            result = asyncio.run(upload_photo_strip_layout(event.id, "festival", count, UploadFile(filename=f"festival-{count}.png", file=BytesIO(_photo_strip_png(count))), db))
            assert result["ok"] is True
            assert result["photo_count"] == count
        enabled = update_photo_strip_settings(event.id, {"enabled": True, "active_theme_id": "festival", "themes": [theme]}, db)
        assert enabled["enabled"] is True
        assert all(enabled["themes"][0]["layouts"][str(count)]["template_name"] for count in (2, 3, 4))


def test_photo_strip_starter_assets_match_each_photo_count():
    assets = Path(__file__).resolve().parents[1] / "frontend" / "assets"
    for count in (2, 3, 4):
        png_path = assets / f"photo-strip-festival-{count}.png"
        pptx_path = assets / f"photo-strip-festival-{count}-canva.pptx"
        image = Image.open(png_path).convert("RGBA")
        assert image.size == (600, 1800)
        alpha = image.getchannel("A")
        for slot in default_photo_strip_slots(count):
            px = round((slot["x"] + slot["width"] / 2) * image.width)
            py = round((slot["y"] + slot["height"] / 2) * image.height)
            assert alpha.getpixel((px, py)) == 0
        with ZipFile(pptx_path) as package:
            assert package.testzip() is None
            slide = package.read("ppt/slides/slide1.xml").decode("utf-8")
            assert slide.count("Photo slot ") >= count
