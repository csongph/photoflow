from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
RAW_EXTENSIONS = {".cr2", ".cr3", ".nef", ".arw"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | RAW_EXTENSIONS


def safe_slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._ -]+", "", value).strip()
    value = re.sub(r"\s+", "_", value)
    return value[:120] or "event"


def sanitize_filename(value: str) -> str:
    name = Path(value).name
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name)
    return name[:180] or "photo"


def unique_path(path: Path) -> Path:
    """Return a non-existing sibling path without deleting or overwriting files."""
    if not path.exists():
        return path
    stem = path.stem[:150]
    suffix = path.suffix
    for idx in range(1, 10_000):
        candidate = path.with_name(f"{stem}_{idx:04d}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not allocate a unique filename for {path.name}")


def is_supported(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def is_raw(path: Path) -> bool:
    return path.suffix.lower() in RAW_EXTENSIONS


def guess_mime(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def wait_until_stable(path: Path, checks: int = 3, interval: float = 0.6, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    stable = 0
    last: tuple[int, int] | None = None
    while time.time() < deadline:
        try:
            stat = path.stat()
        except FileNotFoundError:
            return False
        current = (stat.st_size, stat.st_mtime_ns)
        if current == last and stat.st_size > 0:
            stable += 1
            if stable >= checks:
                return True
        else:
            stable = 0
            last = current
        time.sleep(interval)
    return False


def atomic_copy(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".processing.tmp")
    shutil.copy2(src, tmp)
    os.replace(tmp, dest)


def atomic_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
