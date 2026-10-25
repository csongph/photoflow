from __future__ import annotations

import json
from pathlib import Path

from PIL import Image
from PIL import ImageChops

from local.app.database import Base, SessionLocal, engine, init_db
from local.app.models import Event, Job, Photo, Setting, Upload
from local.app.processing.pipeline import process_photo
from local.app.queue.worker import JobWorker, recover_jobs
from local.app.queue.worker import drive_filename
from local.app.routers.events import delete_event, import_cloud_events, import_finished_photos, retry_failed_job
from local.app.routers.events import publish_photo, update_photo_visibility
from local.app.routers.gallery import pin_ok
from local.app.routers.gallery import photos as gallery_photos
from local.app.utils.files import sha256_file
from local.app.uploader.storage import GoogleAuthorizationExpired
from local.app.watcher.service import IncomingHandler


def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    init_db()


def make_event(tmp_path: Path) -> Event:
    root = tmp_path / "event"
    for dirname in ["INCOMING", "ORIGINAL", "FINISHED", "THUMBNAILS", "PREVIEWS", "CACHE"]:
        (root / dirname).mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        event = Event(
            public_id="public-test",
            name="Test Event",
            slug="test_event",
            root_path=str(root),
            incoming_path=str(root / "INCOMING"),
            auto_correction_json=json.dumps({"auto_exposure": False, "auto_white_balance": False, "highlight_recovery": False, "shadow_recovery": False}),
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        event_id = event.id
    with SessionLocal() as db:
        return db.get(Event, event_id)


def test_process_photo_preserves_original_and_creates_variants(tmp_path: Path):
    reset_db()
    event = make_event(tmp_path)
    original = Path(event.root_path) / "ORIGINAL" / "capture.jpg"
    Image.new("RGB", (1200, 900), "white").save(original, "JPEG", quality=95)
    before = sha256_file(original)
    with SessionLocal() as db:
        event = db.get(Event, event.id)
        photo = Photo(event_id=event.id, capture_id="capture", filename="capture.jpg", original_path=str(original), checksum=before, file_size=original.stat().st_size, status="BACKED_UP")
        db.add(photo)
        db.commit()
        process_photo(db, event, photo)
        db.refresh(photo)
        assert Path(photo.finished_path).exists()
        assert Path(photo.preview_path).exists()
        assert Path(photo.thumbnail_path).exists()
        assert photo.status == "PROCESSED"
    assert sha256_file(original) == before


def test_cloud_event_poll_imports_metadata_idempotently(tmp_path: Path):
    reset_db()
    with SessionLocal() as db:
        db.add(Setting(key="event_root", value=str(tmp_path / "events")))
        db.commit()
        snapshot = [{
            "public_id": "cloud-event-12345678",
            "name": "School Event",
            "event_date": "2026-10-25",
            "description": "Imported from cloud",
            "gallery_settings": {"enable_gallery": True, "allow_download": True},
            "photos": [{
                "local_photo_id": "photo-1",
                "filename": "one.jpg",
                "storage_provider": "google_drive",
                "storage_object_id": "drive-one",
                "published": True,
                "hidden": False,
            }],
        }]
        assert import_cloud_events(db, snapshot) == {"created": 1, "updated": 0, "photos": 1}
        assert import_cloud_events(db, snapshot) == {"created": 0, "updated": 1, "photos": 0}
        event = db.query(Event).filter_by(public_id="cloud-event-12345678").one()
        photo = db.query(Photo).filter_by(event_id=event.id).one()
        assert event.status == "CLOUD"
        assert photo.published is True
        assert photo.storage_object_id == "drive-one"


def test_process_photo_is_passthrough_without_auto_editing(tmp_path: Path):
    reset_db()
    event = make_event(tmp_path)
    original = Path(event.root_path) / "ORIGINAL" / "color.jpg"
    Image.new("RGB", (320, 220), (145, 132, 118)).save(original, "JPEG", quality=96)
    with SessionLocal() as db:
        event = db.get(Event, event.id)
        event.preset_id = "clean_skin"
        event.auto_correction_json = json.dumps({"auto_exposure": True, "auto_white_balance": True, "highlight_recovery": True, "shadow_recovery": True})
        photo = Photo(event_id=event.id, capture_id="color", filename="color.jpg", original_path=str(original), checksum=sha256_file(original), file_size=original.stat().st_size, status="BACKED_UP")
        db.add(photo)
        db.commit()
        process_photo(db, event, photo)
        db.refresh(photo)
        source = Image.open(original).convert("RGB")
        finished = Image.open(photo.finished_path).convert("RGB")
        diff = ImageChops.difference(source, finished)
        assert max(channel[1] for channel in diff.getextrema()) <= 3


def test_watcher_preserves_same_named_distinct_originals(tmp_path: Path):
    reset_db()
    event = make_event(tmp_path)
    incoming = Path(event.incoming_path) / "same.jpg"
    Image.new("RGB", (60, 60), "white").save(incoming)
    handler = IncomingHandler(event.id)
    handler.process_path(incoming)
    first_original = Path(event.root_path) / "ORIGINAL" / "same.jpg"
    first_checksum = sha256_file(first_original)

    Image.new("RGB", (60, 60), "black").save(incoming)
    handler.process_path(incoming)

    second_original = Path(event.root_path) / "ORIGINAL" / "same_0001.jpg"
    assert first_original.exists()
    assert second_original.exists()
    assert sha256_file(first_original) == first_checksum
    assert sha256_file(second_original) != first_checksum


def test_upload_jobs_get_persistent_upload_ids(tmp_path: Path):
    reset_db()
    event = make_event(tmp_path)
    original = Path(event.root_path) / "ORIGINAL" / "capture.jpg"
    Image.new("RGB", (800, 600), "white").save(original, "JPEG", quality=95)
    checksum = sha256_file(original)
    with SessionLocal() as db:
        event = db.get(Event, event.id)
        photo = Photo(event_id=event.id, capture_id="capture", filename="capture.jpg", original_path=str(original), checksum=checksum, file_size=original.stat().st_size, status="BACKED_UP")
        db.add(photo)
        db.commit()
        job = Job(event_id=event.id, photo_id=photo.id, type="PROCESS_PHOTO")
        worker = JobWorker(1)
        worker._process_photo(db, job)
        upload_jobs = db.query(Job).filter(Job.type == "UPLOAD_VARIANT").all()
        uploads = db.query(Upload).all()
        assert len(upload_jobs) == 1
        assert len(uploads) == 1
        assert uploads[0].variant == "finished"
        assert all(json.loads(row.payload_json)["upload_id"] for row in upload_jobs)


def test_drive_required_event_waits_for_uploads_before_publish(tmp_path: Path):
    reset_db()
    event = make_event(tmp_path)
    original = Path(event.root_path) / "ORIGINAL" / "capture.jpg"
    Image.new("RGB", (800, 600), "white").save(original, "JPEG", quality=95)
    checksum = sha256_file(original)
    with SessionLocal() as db:
        event = db.get(Event, event.id)
        event.drive_json = json.dumps({"upload_finished_photos": True})
        photo = Photo(event_id=event.id, capture_id="capture", filename="capture.jpg", original_path=str(original), checksum=checksum, file_size=original.stat().st_size, status="BACKED_UP")
        db.add(photo)
        db.commit()
        job = Job(event_id=event.id, photo_id=photo.id, type="PROCESS_PHOTO")
        worker = JobWorker(1)
        worker._process_photo(db, job)
        assert db.query(Job).filter(Job.type == "UPLOAD_VARIANT").count() == 1
        assert db.query(Job).filter(Job.type == "PUBLISH_PHOTO").count() == 0


def test_finished_upload_is_enough_for_manual_publish(tmp_path: Path):
    reset_db()
    event = make_event(tmp_path)
    with SessionLocal() as db:
        event = db.get(Event, event.id)
        event.drive_json = json.dumps({"upload_finished_photos": True})
        photo = Photo(
            event_id=event.id,
            capture_id="capture",
            filename="capture.jpg",
            checksum="manual-publish-checksum",
            status="PROCESSED",
            finished_path=str(tmp_path / "FINISHED" / "capture.jpg"),
            preview_path=str(tmp_path / "PREVIEWS" / "capture.jpg"),
            thumbnail_path=str(tmp_path / "THUMBNAILS" / "capture.jpg"),
        )
        db.add(photo)
        db.flush()
        db.add(Upload(
            event_id=event.id,
            photo_id=photo.id,
            variant="finished",
            local_path=photo.finished_path,
            state="UPLOADED",
            object_id="drive-file-id",
        ))
        db.commit()

        from local.app.routers.events import required_uploads_done

        assert required_uploads_done(db, photo.id) is True


def test_worker_recovers_uploaded_photo_for_auto_publish(tmp_path: Path):
    reset_db()
    event = make_event(tmp_path)
    with SessionLocal() as db:
        event = db.get(Event, event.id)
        event.drive_json = json.dumps({"upload_finished_photos": True})
        photo = Photo(
            event_id=event.id,
            capture_id="recovery",
            filename="recovery.jpg",
            checksum="recovery-checksum",
            status="PROCESSED",
            finished_path=str(tmp_path / "FINISHED" / "recovery.jpg"),
            preview_path=str(tmp_path / "PREVIEWS" / "recovery.jpg"),
            thumbnail_path=str(tmp_path / "THUMBNAILS" / "recovery.jpg"),
        )
        db.add(photo)
        db.flush()
        db.add(Upload(
            event_id=event.id,
            photo_id=photo.id,
            variant="finished",
            local_path=photo.finished_path,
            state="UPLOADED",
            object_id="recovery-drive-id",
        ))
        db.commit()
        photo_id = photo.id

    worker = JobWorker(1)
    worker._recover_publish_jobs()

    with SessionLocal() as db:
        recovered = db.query(Job).filter(
            Job.photo_id == photo_id,
            Job.type == "PUBLISH_PHOTO",
            Job.state == "QUEUED",
        ).all()
        assert len(recovered) == 1

    worker._recover_publish_jobs()

    with SessionLocal() as db:
        assert db.query(Job).filter(Job.photo_id == photo_id, Job.type == "PUBLISH_PHOTO").count() == 1


def test_reprocess_with_existing_drive_uploads_requeues_publish(tmp_path: Path):
    reset_db()
    event = make_event(tmp_path)
    original = Path(event.root_path) / "ORIGINAL" / "capture.jpg"
    Image.new("RGB", (800, 600), "white").save(original, "JPEG", quality=95)
    checksum = sha256_file(original)
    with SessionLocal() as db:
        event = db.get(Event, event.id)
        event.drive_json = json.dumps({"upload_finished_photos": True})
        event.gallery_json = json.dumps({"instant_publish": True, "review_before_publish": False})
        photo = Photo(event_id=event.id, capture_id="capture", filename="capture.jpg", original_path=str(original), checksum=checksum, file_size=original.stat().st_size, status="BACKED_UP")
        db.add(photo)
        db.flush()
        root = Path(event.root_path)
        for variant, folder in [("thumbnail", "THUMBNAILS"), ("preview", "PREVIEWS"), ("finished", "FINISHED")]:
            local_path = root / folder / "capture.jpg"
            local_path.parent.mkdir(exist_ok=True)
            Image.new("RGB", (200, 100), "white").save(local_path, "JPEG", quality=90)
            db.add(Upload(event_id=event.id, photo_id=photo.id, variant=variant, local_path=str(local_path), state="UPLOADED", object_id=f"{variant}-id"))
        db.commit()

        job = Job(event_id=event.id, photo_id=photo.id, type="PROCESS_PHOTO")
        worker = JobWorker(1)
        worker._process_photo(db, job)
        assert db.query(Job).filter(Job.type == "PUBLISH_PHOTO").count() == 1


def test_review_setting_still_auto_publishes(tmp_path: Path):
    reset_db()
    event = make_event(tmp_path)
    original = Path(event.root_path) / "ORIGINAL" / "capture.jpg"
    Image.new("RGB", (800, 600), "white").save(original, "JPEG", quality=95)
    checksum = sha256_file(original)
    with SessionLocal() as db:
        event = db.get(Event, event.id)
        event.gallery_json = json.dumps({"instant_publish": True, "review_before_publish": True})
        photo = Photo(event_id=event.id, capture_id="capture", filename="capture.jpg", original_path=str(original), checksum=checksum, file_size=original.stat().st_size, status="BACKED_UP")
        db.add(photo)
        db.commit()
        job = Job(event_id=event.id, photo_id=photo.id, type="PROCESS_PHOTO")
        worker = JobWorker(1)
        worker._process_photo(db, job)
        db.refresh(photo)
        assert photo.status == "PROCESSED"
        assert not photo.published
        assert db.query(Job).filter(Job.type == "PUBLISH_PHOTO").count() == 1

        result = publish_photo(event.id, photo.id, db=db)
        db.refresh(photo)
        assert result["published"]
        assert photo.published
        assert photo.status == "PUBLISHED"


def test_photo_visibility_hides_published_photo_from_gallery(tmp_path: Path):
    reset_db()
    event = make_event(tmp_path)
    finished = Path(event.root_path) / "FINISHED" / "capture.jpg"
    preview = Path(event.root_path) / "PREVIEWS" / "capture.jpg"
    thumb = Path(event.root_path) / "THUMBNAILS" / "capture.jpg"
    for path in [finished, preview, thumb]:
        Image.new("RGB", (200, 120), "white").save(path, "JPEG", quality=90)
    with SessionLocal() as db:
        photo = Photo(
            event_id=event.id,
            capture_id="capture",
            filename="capture.jpg",
            finished_path=str(finished),
            preview_path=str(preview),
            thumbnail_path=str(thumb),
            checksum=sha256_file(finished),
            file_size=finished.stat().st_size,
            status="PUBLISHED",
            published=True,
        )
        db.add(photo)
        db.commit()

        result = update_photo_visibility(event.id, photo.id, {"hidden": True}, db=db)
        db.refresh(photo)
        assert result["hidden"]
        assert photo.hidden
        assert photo.status == "HIDDEN"


def test_gallery_uses_local_media_for_display_and_drive_for_download(tmp_path: Path):
    reset_db()
    event = make_event(tmp_path)
    finished = Path(event.root_path) / "FINISHED" / "capture.jpg"
    preview = Path(event.root_path) / "PREVIEWS" / "capture.jpg"
    thumb = Path(event.root_path) / "THUMBNAILS" / "capture.jpg"
    for path in [finished, preview, thumb]:
        Image.new("RGB", (200, 120), "white").save(path, "JPEG", quality=90)
    with SessionLocal() as db:
        photo = Photo(
            event_id=event.id,
            capture_id="capture",
            filename="capture.jpg",
            finished_path=str(finished),
            preview_path=str(preview),
            thumbnail_path=str(thumb),
            checksum=sha256_file(finished),
            file_size=finished.stat().st_size,
            status="PUBLISHED",
            published=True,
        )
        db.add(photo)
        db.flush()
        db.add(Upload(event_id=event.id, photo_id=photo.id, variant="thumbnail", local_path=str(thumb), state="UPLOADED", object_id="thumb-drive-id"))
        db.add(Upload(event_id=event.id, photo_id=photo.id, variant="preview", local_path=str(preview), state="UPLOADED", object_id="preview-drive-id"))
        db.add(Upload(event_id=event.id, photo_id=photo.id, variant="finished", local_path=str(finished), state="UPLOADED", object_id="finished-drive-id"))
        db.commit()

        rows = gallery_photos(event.public_id, db=db)
        variants = {item["kind"]: item for item in rows[0]["variants"]}
        assert variants["thumbnail"]["url"].startswith(f"/media/{event.id}/THUMBNAILS/")
        assert variants["preview"]["url"].startswith(f"/media/{event.id}/PREVIEWS/")
        assert variants["finished"]["url"].startswith(f"/api/gallery/{event.public_id}/photos/{photo.id}/download")


def test_drive_upload_name_is_flat_inside_root_folder(tmp_path: Path):
    reset_db()
    event = make_event(tmp_path)
    event.name = "งาน รูปนักเรียน"
    event.slug = "student-photo-day"
    upload = Upload(event_id=event.id, photo_id="photo", variant="finished", local_path=str(tmp_path / "DSC_0959.jpg"))
    key = drive_filename(event, upload)
    assert "/" not in key
    assert "\\" not in key
    assert key == "student-photo-day__DSC_0959.jpg"


def test_gallery_optional_pin():
    event = Event(public_id="public-test", name="Pinned", slug="pinned", root_path="", incoming_path="", gallery_json=json.dumps({"optional_pin": "1234"}))
    assert pin_ok(event, "1234")
    assert not pin_ok(event, "")


def test_delete_event_removes_database_rows_and_event_folder(tmp_path: Path, monkeypatch):
    reset_db()
    monkeypatch.setattr("local.app.routers.events.cloud_sync_enabled", lambda: False)
    event = make_event(tmp_path)
    marker = Path(event.root_path) / "event.json"
    marker.write_text("{}", encoding="utf-8")
    with SessionLocal() as db:
        event = db.get(Event, event.id)
        photo = Photo(event_id=event.id, capture_id="delete-me", filename="delete.jpg", checksum="abc", file_size=1)
        db.add(photo)
        db.flush()
        db.add(Job(event_id=event.id, photo_id=photo.id, type="PROCESS_PHOTO"))
        db.add(Upload(event_id=event.id, photo_id=photo.id, variant="finished", local_path=str(marker)))
        db.commit()

        result = delete_event(event.id, delete_files=True, db=db)
        assert result["ok"]
        assert result["deleted_files"]
        assert db.get(Event, event.id) is None
        assert db.query(Photo).count() == 0
        assert db.query(Job).count() == 0
        assert db.query(Upload).count() == 0
    assert not Path(event.root_path).exists()


def test_unconfigured_storage_marks_upload_ready_without_failure(tmp_path: Path):
    reset_db()
    event = make_event(tmp_path)
    variant = Path(event.root_path) / "FINISHED" / "capture.jpg"
    Image.new("RGB", (200, 100), "white").save(variant, "JPEG", quality=90)
    with SessionLocal() as db:
        photo = Photo(event_id=event.id, capture_id="capture", filename="capture.jpg", original_path=str(variant), checksum=sha256_file(variant), file_size=variant.stat().st_size)
        db.add(photo)
        db.flush()
        upload = Upload(event_id=event.id, photo_id=photo.id, variant="finished", local_path=str(variant))
        db.add(upload)
        db.flush()
        job = Job(event_id=event.id, photo_id=photo.id, type="UPLOAD_VARIANT", payload_json=json.dumps({"upload_id": upload.id}))
        db.add(job)
        db.commit()

        worker = JobWorker(1)
        assert worker._handle_one()
        db.refresh(upload)
        db.refresh(job)
        assert upload.state == "READY_TO_UPLOAD"
        assert job.state == "PROCESSED"


def test_expired_google_token_disconnects_and_parks_upload(tmp_path: Path, monkeypatch):
    reset_db()
    event = make_event(tmp_path)
    variant = Path(event.root_path) / "FINISHED" / "capture.jpg"
    Image.new("RGB", (200, 100), "white").save(variant, "JPEG", quality=90)

    class ExpiredProvider:
        configured = True

        def upload_file(self, local_path, remote_key, mime_type):
            raise GoogleAuthorizationExpired("Google Drive authorization expired; reconnect Google Drive")

    monkeypatch.setattr("local.app.queue.worker.env_provider", lambda refresh_token, root_folder: ExpiredProvider())
    with SessionLocal() as db:
        db.add(Setting(key="google_refresh_token", value="revoked-token"))
        photo = Photo(event_id=event.id, capture_id="capture", filename="capture.jpg", original_path=str(variant), checksum=sha256_file(variant), file_size=variant.stat().st_size)
        db.add(photo)
        db.flush()
        upload = Upload(event_id=event.id, photo_id=photo.id, variant="finished", local_path=str(variant))
        db.add(upload)
        db.flush()
        job = Job(event_id=event.id, photo_id=photo.id, type="UPLOAD_VARIANT", payload_json=json.dumps({"upload_id": upload.id}))
        db.add(job)
        db.commit()

        assert JobWorker(1)._handle_one()
        db.refresh(upload)
        db.refresh(job)
        assert db.get(Setting, "google_refresh_token").value == ""
        assert upload.state == "READY_TO_UPLOAD"
        assert "reconnect" in upload.error
        assert job.state == "PROCESSED"


def test_successful_drive_upload_queues_auto_publish(tmp_path: Path, monkeypatch):
    reset_db()
    event = make_event(tmp_path)
    variant = Path(event.root_path) / "FINISHED" / "capture.jpg"
    Image.new("RGB", (200, 100), "white").save(variant, "JPEG", quality=90)

    class FakeProvider:
        name = "google_drive"
        configured = True

        def upload_file(self, local_path, remote_key, mime_type):
            return {"id": "uploaded-drive-id"}

    monkeypatch.setattr("local.app.queue.worker.env_provider", lambda refresh_token, root_folder: FakeProvider())
    monkeypatch.setattr("local.app.queue.worker.sync_photo", lambda event, photo, **kwargs: True)

    with SessionLocal() as db:
        event = db.get(Event, event.id)
        event.drive_json = json.dumps({"upload_finished_photos": True})
        photo = Photo(
            event_id=event.id,
            capture_id="capture",
            filename="capture.jpg",
            original_path=str(variant),
            finished_path=str(variant),
            preview_path=str(variant),
            thumbnail_path=str(variant),
            checksum=sha256_file(variant),
            file_size=variant.stat().st_size,
            status="PROCESSED",
        )
        db.add(photo)
        db.flush()
        upload = Upload(event_id=event.id, photo_id=photo.id, variant="finished", local_path=str(variant))
        db.add(upload)
        db.flush()
        db.add(Job(
            event_id=event.id,
            photo_id=photo.id,
            type="UPLOAD_VARIANT",
            payload_json=json.dumps({"upload_id": upload.id}),
        ))
        db.commit()
        photo_id = photo.id

    worker = JobWorker(1)
    assert worker._handle_one()

    with SessionLocal() as db:
        upload = db.query(Upload).filter(Upload.photo_id == photo_id).one()
        publish_jobs = db.query(Job).filter(
            Job.photo_id == photo_id,
            Job.type == "PUBLISH_PHOTO",
            Job.state == "QUEUED",
        ).all()
        assert upload.state == "UPLOADED"
        assert upload.object_id == "uploaded-drive-id"
        assert len(publish_jobs) == 1

    assert worker._handle_one()

    with SessionLocal() as db:
        photo = db.get(Photo, photo_id)
        publish_job = db.query(Job).filter(Job.photo_id == photo_id, Job.type == "PUBLISH_PHOTO").one()
        assert photo.published is True
        assert photo.status == "PUBLISHED"
        assert publish_job.state == "PROCESSED"


def test_recover_jobs_requeues_in_progress(tmp_path: Path):
    reset_db()
    event = make_event(tmp_path)
    with SessionLocal() as db:
        db.add(Job(event_id=event.id, type="PROCESS_PHOTO", state="PROCESSING"))
        db.add(Job(event_id=event.id, type="UPLOAD_VARIANT", state="UPLOADING"))
        db.commit()
    recover_jobs()
    with SessionLocal() as db:
        assert {job.state for job in db.query(Job).all()} == {"RETRYING"}


def test_imported_finished_photo_enters_real_processing_queue(tmp_path: Path):
    reset_db()
    event = make_event(tmp_path)
    source = Path(event.root_path) / "FINISHED" / "imported.jpg"
    Image.new("RGB", (320, 200), "white").save(source, "JPEG", quality=90)

    with SessionLocal() as db:
        event = db.get(Event, event.id)
        assert import_finished_photos(db, event) == 1
        db.commit()

        photo = db.query(Photo).one()
        job = db.query(Job).one()
        assert photo.original_path == str(source)
        assert photo.status == "QUEUED"
        assert photo.published is False
        assert job.type == "PROCESS_PHOTO"
        assert job.photo_id == photo.id


def test_retry_failed_job_resets_attempt_budget(tmp_path: Path):
    reset_db()
    event = make_event(tmp_path)
    with SessionLocal() as db:
        job = Job(event_id=event.id, type="SYNC_EVENT", state="FAILED", attempts=5, error="network")
        db.add(job)
        db.commit()

        result = retry_failed_job(event.id, job.id, db=db)
        db.refresh(job)
        assert result["ok"]
        assert job.state == "RETRYING"
        assert job.attempts == 0
        assert job.error == ""
