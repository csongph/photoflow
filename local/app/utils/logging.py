from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from ..config import settings


def configure_logging() -> None:
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("photoflow")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    file_handler = RotatingFileHandler(settings.logs_dir / "photoflow.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

