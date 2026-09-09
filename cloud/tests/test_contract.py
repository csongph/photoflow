import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

pytestmark = pytest.mark.cloud

pytest.importorskip("psycopg")
from cloud.app.main import app
from cloud.app.models import Event, PhotoVariant
from cloud.app.routers.gallery import pin_ok, variant_url
from cloud.app.routers.sync import pin_hash, require_sync_token


def test_app_exists():
    assert app.title == "MomentLink Cloud"


def test_render_head_health_checks():
    client = TestClient(app)

    assert client.head("/").status_code == 200
    assert client.head("/healthz").status_code == 200


def test_finished_drive_file_uses_image_urls_for_derived_variants():
    variant = PhotoVariant(
        photo_id="photo-id",
        kind="finished",
        storage_provider="google_drive",
        storage_object_id="drive-file-id",
    )

    assert variant_url(variant, "thumbnail") == "https://drive.google.com/thumbnail?id=drive-file-id&sz=w500"
    assert variant_url(variant, "preview") == "https://drive.google.com/thumbnail?id=drive-file-id&sz=w1600"
    assert variant_url(variant, "finished") == "https://drive.google.com/uc?export=download&id=drive-file-id"


def test_cloud_gallery_pin_is_hashed_and_checked():
    event = Event(public_id="public-id", name="Pinned", pin_hash=pin_hash("123456"))

    assert pin_ok(event, "123456")
    assert not pin_ok(event, "000000")


def test_cloud_sync_fails_closed_without_token(monkeypatch):
    monkeypatch.delenv("CLOUD_SYNC_TOKEN", raising=False)

    with pytest.raises(HTTPException) as exc:
        require_sync_token("")

    assert exc.value.status_code == 503
