from __future__ import annotations

import logging
import shutil
import threading
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from ..database import SessionLocal
from ..models import Event, Job, Photo
from ..utils.files import atomic_copy, guess_mime, is_raw, is_supported, sanitize_filename, sha256_file, unique_path, wait_until_stable

log = logging.getLogger("photoflow")


class IncomingHandler(FileSystemEventHandler):
    def __init__(self, event_id: str):
        self.event_id = event_id
        self._lock = threading.Lock()
        self._processing: set[Path] = set()

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            threading.Thread(target=self.process_path, args=(Path(event.src_path),), daemon=True).start()

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            threading.Thread(target=self.process_path, args=(Path(event.src_path),), daemon=True).start()

    def process_path(self, path: Path) -> None:
        path = path.resolve()
        if path.name.endswith(".processing.tmp") or not is_supported(path):
            return
        with self._lock:
            if path in self._processing:
                return
            self._processing.add(path)
        try:
            if not wait_until_stable(path):
                log.warning("File did not become stable: %s", path)
                return
            with SessionLocal() as db:
                event = db.get(Event, self.event_id)
                if not event:
                    return
                checksum = sha256_file(path)
                existing = db.query(Photo).filter(Photo.event_id == event.id, Photo.checksum == checksum).first()
                if existing:
                    return
                filename = sanitize_filename(path.name)
                capture_id = path.stem.lower()
                original_dir = Path(event.root_path) / "ORIGINAL"
                original_path = unique_path(original_dir / filename)
                atomic_copy(path, original_path)
                filename = original_path.name
                photo = Photo(
                    event_id=event.id,
                    capture_id=capture_id,
                    filename=filename,
                    original_path=str(original_path),
                    checksum=checksum,
                    file_size=path.stat().st_size,
                    mime_type=guess_mime(path),
                    raw_path=str(original_path) if is_raw(path) else "",
                    status="BACKED_UP",
                )
                db.add(photo)
                try:
                    db.flush()
                    if is_raw(path):
                        photo.status = "FAILED"
                        photo.error = "RAW preserved. Gallery processing waits for a JPEG pair or rawpy support."
                    else:
                        db.add(Job(event_id=event.id, photo_id=photo.id, type="PROCESS_PHOTO", priority=20))
                        photo.status = "QUEUED"
                    db.commit()
                except IntegrityError:
                    db.rollback()
                    if original_path.exists():
                        log.info("Duplicate capture ignored after original backup: %s", original_path)
        finally:
            with self._lock:
                self._processing.discard(path)


class WatcherManager:
    def __init__(self):
        self.observers: dict[str, Observer] = {}

    def start_event(self, event: Event) -> None:
        if event.id in self.observers:
            return
        incoming = Path(event.incoming_path)
        incoming.mkdir(parents=True, exist_ok=True)
        handler = IncomingHandler(event.id)
        observer = Observer()
        observer.schedule(handler, str(incoming), recursive=False)
        observer.start()
        self.observers[event.id] = observer
        for path in incoming.iterdir():
            if path.is_file():
                threading.Thread(target=handler.process_path, args=(path,), daemon=True).start()

    def stop_event(self, event_id: str) -> None:
        observer = self.observers.pop(event_id, None)
        if observer:
            observer.stop()
            observer.join(timeout=3)

    def stop_all(self) -> None:
        for event_id in list(self.observers):
            self.stop_event(event_id)


watcher_manager = WatcherManager()
