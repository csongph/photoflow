from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import and_, select

from ..database import SessionLocal
from ..models import Event, Job, Photo, Setting, Upload
from ..processing.pipeline import UnsupportedRawError, process_photo
from ..sync.cloud import enabled as cloud_sync_enabled, list_cloud_events, sync_event, sync_photo
from ..uploader.storage import GoogleAuthorizationExpired, env_provider

log = logging.getLogger("photoflow")


REQUIRED_GALLERY_UPLOADS = {"finished", "preview", "thumbnail"}


def drive_required(event: Event) -> bool:
    try:
        drive = json.loads(event.drive_json or "{}")
    except json.JSONDecodeError:
        drive = {}
    return bool(drive.get("upload_finished_photos"))


def auto_publish_enabled(event: Event) -> bool:
    return True


def drive_filename(event: Event | None, upload: Upload) -> str:
    source = Path(upload.local_path)
    event_name = (event.slug if event and event.slug else event.name if event else upload.event_id).strip()
    safe_event = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in event_name)[:70] or "event"
    return f"{safe_event}__{source.name}"


class JobWorker:
    def __init__(self, worker_count: int = 2):
        self.worker_count = max(1, min(worker_count, 6))
        self.stop_event = threading.Event()
        self.threads: list[threading.Thread] = []
        self._claim_lock = threading.Lock()
        self._cloud_poll_thread: threading.Thread | None = None
        self._last_cloud_poll = 0.0

    def start(self) -> None:
        if self.threads:
            return
        self._recover_publish_jobs()
        self._cloud_poll_thread = threading.Thread(target=self._poll_cloud_events, name="photoflow-cloud-events", daemon=True)
        self._cloud_poll_thread.start()
        for idx in range(self.worker_count):
            thread = threading.Thread(target=self._run, name=f"photoflow-worker-{idx}", daemon=True)
            thread.start()
            self.threads.append(thread)

    def _recover_publish_jobs(self) -> None:
        with SessionLocal() as db:
            photos = db.query(Photo).filter(
                Photo.published == False,
                Photo.hidden == False,
                Photo.status.in_(["PROCESSED", "AWAITING_REVIEW"]),
                Photo.finished_path != "",
            ).all()
            for photo in photos:
                event = db.get(Event, photo.event_id)
                if not event or event.publishing_paused or not auto_publish_enabled(event):
                    continue
                if drive_required(event) and not self._required_uploads_done(db, photo.id):
                    continue
                pending = db.query(Job).filter(
                    Job.photo_id == photo.id,
                    Job.type == "PUBLISH_PHOTO",
                    Job.state.in_(["QUEUED", "RETRYING", "PROCESSING"]),
                ).first()
                if not pending:
                    db.add(Job(event_id=event.id, photo_id=photo.id, type="PUBLISH_PHOTO", priority=70))
            db.commit()

    def stop(self) -> None:
        self.stop_event.set()
        for thread in self.threads:
            thread.join(timeout=2)
        if self._cloud_poll_thread:
            self._cloud_poll_thread.join(timeout=2)

    def _poll_cloud_events(self) -> None:
        try:
            interval = min(3600, max(30, int(os.getenv("CLOUD_EVENT_POLL_SECONDS", "60"))))
        except ValueError:
            interval = 60
            log.warning("Invalid CLOUD_EVENT_POLL_SECONDS; using 60 seconds")
        while not self.stop_event.is_set():
            if cloud_sync_enabled():
                try:
                    from ..routers.events import import_cloud_events
                    with SessionLocal() as db:
                        result = import_cloud_events(db, list_cloud_events(strict=True))
                    if result["created"] or result["updated"]:
                        log.info("Cloud event poll: imported %s new event(s), updated %s", result["created"], result["updated"])
                except Exception:
                    log.exception("Cloud event poll failed; will retry")
            self.stop_event.wait(interval)

    def _run(self) -> None:
        while not self.stop_event.is_set():
            handled = self._handle_one()
            if not handled:
                time.sleep(0.7)

    def _claim_job(self, db) -> Job | None:
        with self._claim_lock:
            job = db.execute(
                select(Job)
                .where(and_(Job.state.in_(["QUEUED", "RETRYING"]), Job.available_at <= datetime.utcnow()))
                .order_by(Job.priority.asc(), Job.created_at.asc())
                .limit(1)
            ).scalar_one_or_none()
            if not job:
                return None
            job.state = "PROCESSING"
            job.attempts += 1
            db.commit()
            db.refresh(job)
            return job

    def _handle_one(self) -> bool:
        with SessionLocal() as db:
            job = self._claim_job(db)
            if not job:
                return False
            try:
                if job.type == "PROCESS_PHOTO":
                    self._process_photo(db, job)
                elif job.type == "UPLOAD_VARIANT":
                    self._upload_variant(db, job)
                elif job.type == "PUBLISH_PHOTO":
                    self._publish_photo(db, job)
                elif job.type == "SYNC_EVENT":
                    self._sync_event(db, job)
                elif job.type == "SYNC_PHOTO":
                    self._sync_photo(db, job)
                job.state = "PROCESSED"
                db.commit()
            except Exception as exc:
                log.exception("Job failed: %s", job.id)
                self._fail_or_retry(db, job, str(exc))
            return True

    def _process_photo(self, db, job: Job) -> None:
        event = db.get(Event, job.event_id)
        photo = db.get(Photo, job.photo_id)
        if not event or not photo:
            raise RuntimeError("Missing event or photo")
        try:
            photo.status = "PROCESSING"
            db.commit()
            process_photo(db, event, photo)
        except UnsupportedRawError as exc:
            photo.status = "FAILED"
            photo.error = str(exc)
            db.commit()
            return
        for variant, local_path in (("finished", photo.finished_path), ("preview", photo.preview_path), ("thumbnail", photo.thumbnail_path)):
            if not local_path:
                continue
            upload = db.query(Upload).filter(Upload.photo_id == photo.id, Upload.variant == variant).first()
            if not upload:
                upload = Upload(event_id=event.id, photo_id=photo.id, variant=variant, local_path=local_path)
                db.add(upload)
                db.flush()
            else:
                upload.local_path = local_path
                upload.object_id = ""
                upload.state = "QUEUED"
                upload.error = ""
            db.add(Job(event_id=event.id, photo_id=photo.id, type="UPLOAD_VARIANT", priority=30, payload_json=json.dumps({"upload_id": upload.id})))
        if drive_required(event) and self._required_uploads_done(db, photo.id):
            if auto_publish_enabled(event) and not event.publishing_paused:
                db.add(Job(event_id=event.id, photo_id=photo.id, type="PUBLISH_PHOTO", priority=70))
            elif not auto_publish_enabled(event):
                photo.status = "AWAITING_REVIEW"
        elif not drive_required(event) and not event.publishing_paused and auto_publish_enabled(event):
            db.add(Job(event_id=event.id, photo_id=photo.id, type="PUBLISH_PHOTO", priority=70))
        elif not drive_required(event) and not auto_publish_enabled(event):
            photo.status = "AWAITING_REVIEW"
        db.commit()

    def _upload_variant(self, db, job: Job) -> None:
        payload = json.loads(job.payload_json or "{}")
        upload = db.get(Upload, payload.get("upload_id"))
        if not upload:
            return
        if upload.state == "UPLOADED" and upload.object_id:
            return
        if not Path(upload.local_path).exists():
            raise RuntimeError("Variant file is missing")
        refresh_token = (db.get(Setting, "google_refresh_token").value if db.get(Setting, "google_refresh_token") else "")
        root_folder = (db.get(Setting, "drive_root").value if db.get(Setting, "drive_root") else "CS.BXXM Events")
        provider = env_provider(refresh_token, root_folder)
        if not provider.configured:
            upload.state = "READY_TO_UPLOAD"
            upload.error = "Google Drive is not connected; waiting for setup."
            db.commit()
            return
        event = db.get(Event, upload.event_id)
        photo = db.get(Photo, upload.photo_id)
        remote_key = drive_filename(event, upload)
        upload.state = "UPLOADING"
        db.commit()
        try:
            result = provider.upload_file(Path(upload.local_path), remote_key, "")
        except GoogleAuthorizationExpired as exc:
            token_setting = db.get(Setting, "google_refresh_token")
            if token_setting:
                token_setting.value = ""
            upload.state = "READY_TO_UPLOAD"
            upload.error = str(exc)
            db.commit()
            log.warning("Google Drive authorization expired; uploads paused until reconnect")
            return
        upload.state = "UPLOADED"
        upload.object_id = result["id"]
        upload.error = ""
        all_gallery_files_uploaded = False
        if photo:
            photo.storage_provider = provider.name
            if upload.variant == "finished":
                photo.storage_object_id = result["id"]
            elif upload.variant == "thumbnail":
                photo.thumbnail_object_id = result["id"]
            elif upload.variant == "preview":
                photo.preview_object_id = result["id"]
            # SessionLocal disables autoflush, so persist the completed upload
            # before checking whether every required file is ready to publish.
            db.flush()
            all_gallery_files_uploaded = bool(event and drive_required(event) and self._required_uploads_done(db, photo.id))
            if all_gallery_files_uploaded and not photo.published:
                if auto_publish_enabled(event):
                    db.add(Job(event_id=event.id, photo_id=photo.id, type="PUBLISH_PHOTO", priority=70))
                else:
                    photo.status = "AWAITING_REVIEW"
            elif all_gallery_files_uploaded and photo.published and cloud_sync_enabled():
                pending_sync = db.query(Job).filter(
                    Job.event_id == event.id,
                    Job.photo_id == photo.id,
                    Job.type == "SYNC_PHOTO",
                    Job.state.in_(["QUEUED", "RETRYING", "PROCESSING"]),
                ).first()
                if not pending_sync:
                    db.add(Job(event_id=event.id, photo_id=photo.id, type="SYNC_PHOTO", priority=60))
        db.commit()

    def _publish_photo(self, db, job: Job) -> None:
        event = db.get(Event, job.event_id)
        photo = db.get(Photo, job.photo_id)
        if not event or not photo:
            return
        if drive_required(event) and not self._required_uploads_done(db, photo.id):
            job.state = "RETRYING"
            job.available_at = datetime.utcnow() + timedelta(seconds=20)
            db.commit()
            raise RuntimeError("Waiting for Google Drive uploads before publishing")
        if event.publishing_paused:
            job.state = "RETRYING"
            job.available_at = datetime.utcnow() + timedelta(seconds=15)
            db.commit()
            raise RuntimeError("Publishing is paused")
        if not auto_publish_enabled(event):
            photo.status = "AWAITING_REVIEW"
            db.commit()
            return
        photo.published = True
        photo.hidden = False
        photo.status = "PUBLISHED"
        db.commit()
        sync_photo(event, photo, strict=cloud_sync_enabled())

    def _sync_event(self, db, job: Job) -> None:
        event = db.get(Event, job.event_id)
        if event:
            sync_event(event, strict=cloud_sync_enabled())

    def _sync_photo(self, db, job: Job) -> None:
        event = db.get(Event, job.event_id)
        photo = db.get(Photo, job.photo_id)
        if event and photo:
            sync_photo(event, photo, strict=cloud_sync_enabled())

    def _required_uploads_done(self, db, photo_id: str) -> bool:
        uploaded = {
            upload.variant
            for upload in db.query(Upload).filter(
                Upload.photo_id == photo_id,
                Upload.variant.in_(REQUIRED_GALLERY_UPLOADS),
                Upload.state == "UPLOADED",
                Upload.object_id != "",
            )
        }
        return REQUIRED_GALLERY_UPLOADS.issubset(uploaded)

    def _fail_or_retry(self, db, job: Job, error: str) -> None:
        job.error = error[:2000]
        if job.attempts < job.max_attempts:
            job.state = "RETRYING"
            job.available_at = datetime.utcnow() + timedelta(seconds=min(1800, 2 ** job.attempts))
        else:
            job.state = "FAILED"
            photo = db.get(Photo, job.photo_id) if job.photo_id else None
            if photo and not photo.finished_path:
                photo.status = "FAILED"
                photo.error = error[:2000]
        db.commit()


def recover_jobs() -> None:
    with SessionLocal() as db:
        for job in db.execute(select(Job).where(Job.state.in_(["PROCESSING", "UPLOADING", "UPLOADING_VARIANT"]))).scalars():
            job.state = "RETRYING"
            job.available_at = datetime.utcnow()
        db.commit()
