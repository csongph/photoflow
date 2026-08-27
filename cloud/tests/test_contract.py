import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.cloud

pytest.importorskip("psycopg")
from cloud.app.main import app
from cloud.app.models import PhotoVariant
from cloud.app.routers.gallery import variant_url


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
