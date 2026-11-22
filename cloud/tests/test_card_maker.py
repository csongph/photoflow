from __future__ import annotations

import hashlib
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cloud.app.database import Base, get_db
from cloud.app.main import app


def _card_template() -> bytes:
    image = Image.new("RGBA", (600, 1800), (31, 22, 48, 255))
    draw = ImageDraw.Draw(image)
    for index in range(4):
        top = round((.16 + index * .19) * image.height)
        bottom = round((.16 + index * .19 + .165) * image.height)
        draw.rectangle((72, top, 528, bottom), fill=(0, 0, 0, 0))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _photo_strip_template(count: int) -> bytes:
    image = Image.new("RGBA", (600, 1800), (31, 22, 48, 255))
    if count == 4:
        slots = [(0.12, 0.16 + index * 0.19, 0.76, 0.165) for index in range(4)]
    else:
        height, gap = ({2: (.27, .07), 3: (.205, .05)})[count]
        top = (1 - count * height - (count - 1) * gap) / 2
        slots = [(.12, top + index * (height + gap), .76, height) for index in range(count)]
    draw = ImageDraw.Draw(image)
    for x, y, width, height in slots:
        draw.rectangle((round(x * image.width), round(y * image.height), round((x + width) * image.width), round((y + height) * image.height)), fill=(0, 0, 0, 0))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


@pytest.fixture
def cloud_client(tmp_path, monkeypatch):
    database_path = tmp_path / "cloud-card-maker.sqlite"
    engine = create_engine(f"sqlite:///{database_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    test_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        with test_session() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setenv("CLOUD_SYNC_TOKEN", "test-card-maker-token")
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


def test_cloud_card_template_sync_enable_disable_and_pin_access(cloud_client: TestClient):
    public_id = "cloud-card-maker-test-001"
    token = {"Authorization": "Bearer test-card-maker-token"}
    pin = "7391"
    created = cloud_client.post(
        "/api/sync/event",
        headers=token,
        json={
            "public_id": public_id,
            "name": "Card Maker Test",
            "gallery_settings": {
                "enable_gallery": True,
                "allow_download": True,
                "card_maker_enabled": False,
                "card_template_name": "",
                "pin_hash": hashlib.sha256(pin.encode()).hexdigest(),
            },
        },
    )
    assert created.status_code == 200

    template = _card_template()
    upload = cloud_client.post(
        f"/api/sync/events/{public_id}/card-template",
        headers=token,
        data={"enabled": "true"},
        files={"template": ("festival-card.png", template, "image/png")},
    )
    assert upload.status_code == 200, upload.text

    locked_gallery = cloud_client.get(f"/api/gallery/{public_id}")
    assert locked_gallery.status_code == 200
    assert locked_gallery.json()["settings"]["locked"] is True
    assert locked_gallery.json()["settings"]["card_maker_enabled"] is False
    assert cloud_client.get(f"/api/gallery/{public_id}/card-template.png").status_code == 403

    unlocked = cloud_client.post(f"/api/gallery/{public_id}/unlock", json={"pin": pin})
    assert unlocked.status_code == 200
    assert unlocked.json()["ok"] is True
    gallery = cloud_client.get(f"/api/gallery/{public_id}")
    assert gallery.json()["settings"]["card_maker_enabled"] is True
    downloaded_template = cloud_client.get(f"/api/gallery/{public_id}/card-template.png")
    assert downloaded_template.status_code == 200
    assert downloaded_template.content == template
    assert downloaded_template.headers["content-type"].startswith("image/png")

    disabled_upload = cloud_client.post(
        f"/api/sync/events/{public_id}/card-template",
        headers=token,
        data={"enabled": "false"},
        files={"template": ("festival-card.png", template, "image/png")},
    )
    assert disabled_upload.status_code == 200
    assert cloud_client.get(f"/api/gallery/{public_id}").json()["settings"]["card_maker_enabled"] is False
    assert cloud_client.get(f"/api/gallery/{public_id}/card-template.png").status_code == 404

    cloud_client.cookies.clear()
    assert cloud_client.get(f"/api/gallery/{public_id}").json()["settings"]["locked"] is True


def test_photo_strip_requires_admin_enable_and_all_layout_assets(cloud_client: TestClient):
    public_id = "cloud-photo-strip-test-001"
    token = {"Authorization": "Bearer test-card-maker-token"}
    theme_id = "festival"
    layouts = {}
    for count in (2, 3, 4):
        if count == 4:
            slots = [{"x": .12, "y": round(.16 + i * .19, 4), "width": .76, "height": .165} for i in range(4)]
        else:
            height, gap = ({2: (.27, .07), 3: (.205, .05)})[count]
            top = (1 - count * height - (count - 1) * gap) / 2
            slots = [{"x": .12, "y": round(top + i * (height + gap), 4), "width": .76, "height": height} for i in range(count)]
        layouts[str(count)] = {"slots": slots, "template_name": f"{count}.png"}
    config = {"enabled": True, "active_theme_id": theme_id, "themes": [{"id": theme_id, "name": "Festival", "description": "", "background_color": "#FFFFFF", "accent_color": "#E98672", "text_color": "#33283F", "caption": "", "layouts": layouts}]}
    created = cloud_client.post("/api/sync/event", headers=token, json={"public_id": public_id, "name": "Photo Strip Test", "gallery_settings": {"enable_gallery": True, "allow_download": True, "photo_strip_enabled": True, "photo_strip_config_json": __import__("json").dumps(config)}})
    assert created.status_code == 200, created.text
    assert cloud_client.get(f"/api/gallery/{public_id}").json()["settings"]["photo_strip_enabled"] is False

    for count in (2, 3, 4):
        response = cloud_client.post(f"/api/sync/events/{public_id}/photo-strip-asset", headers=token, data={"theme_id": theme_id, "photo_count": str(count)}, files={"template": (f"{count}.png", _photo_strip_template(count), "image/png")})
        assert response.status_code == 200, response.text
    gallery = cloud_client.get(f"/api/gallery/{public_id}").json()
    assert gallery["settings"]["photo_strip_enabled"] is True
    assert all(gallery["settings"]["photo_strip_theme"]["layouts"][str(count)]["asset_present"] for count in (2, 3, 4))
    result = cloud_client.get(f"/api/gallery/{public_id}/photo-strip/{theme_id}/3.png")
    assert result.status_code == 200
    assert result.headers["content-type"].startswith("image/png")

    settings = cloud_client.post("/api/sync/event", headers=token, json={"public_id": public_id, "name": "Photo Strip Test", "gallery_settings": {"enable_gallery": True, "allow_download": True, "photo_strip_enabled": False, "photo_strip_config_json": __import__("json").dumps(config)}})
    assert settings.status_code == 200
    assert cloud_client.get(f"/api/gallery/{public_id}").json()["settings"]["photo_strip_enabled"] is False
    assert cloud_client.get(f"/api/gallery/{public_id}/photo-strip/{theme_id}/3.png").status_code == 404

