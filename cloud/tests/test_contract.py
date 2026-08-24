import pytest

pytestmark = pytest.mark.cloud

pytest.importorskip("psycopg")
from cloud.app.main import app


def test_app_exists():
    assert app.title == "PhotoFlow Cloud"
