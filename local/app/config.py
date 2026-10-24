from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel


BASE_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BASE_DIR.parent
load_dotenv(PROJECT_DIR / ".env")


class Settings(BaseModel):
    local_host: str = os.getenv("LOCAL_HOST", "127.0.0.1")
    local_port: int = int(os.getenv("LOCAL_PORT", "8000"))
    cloud_api_url: str = os.getenv("CLOUD_API_URL", "")
    public_gallery_base_url: str = os.getenv("PUBLIC_GALLERY_BASE_URL", "http://127.0.0.1:8000/gallery")
    database_url: str = os.getenv("LOCAL_DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'photoflow.db'}")
    event_root: Path = Path(os.getenv("EVENT_ROOT_DIR", str(BASE_DIR / "events")))
    data_dir: Path = BASE_DIR / "data"
    logs_dir: Path = BASE_DIR / "logs"
    frontend_dir: Path = BASE_DIR / "frontend"
    jpeg_quality: int = int(os.getenv("JPEG_QUALITY", "90"))
    max_workers: int = int(os.getenv("WORKER_COUNT", "2"))
    auto_open_browser: bool = os.getenv("AUTO_OPEN_BROWSER", "true").lower() == "true"
    # Face search is intentionally disabled in V1; the public workflow does not expose it.
    face_search_enabled: bool = os.getenv("FACE_SEARCH_ENABLED", "false").lower() == "true"


settings = Settings()


def ensure_directories() -> None:
    for path in (settings.data_dir, settings.logs_dir, settings.event_root):
        path.mkdir(parents=True, exist_ok=True)

