from __future__ import annotations

from pathlib import Path

from PIL import Image
from PIL import ImageStat

from local.app.processing.corrections import apply_natural_corrections
from local.app.processing.pipeline import fit_long_edge, open_source_image, save_jpeg_atomic
from local.app.security import make_session, valid_session
from local.app.utils.files import atomic_copy, safe_slug, sha256_file, unique_path, wait_until_stable


def test_safe_slug():
    assert safe_slug("Freshy 2026 !!") == "Freshy_2026"


def test_file_stability_and_checksum(tmp_path: Path):
    path = tmp_path / "a.jpg"
    Image.new("RGB", (20, 20), "white").save(path)
    assert wait_until_stable(path, checks=1, interval=0.01)
    assert len(sha256_file(path)) == 64


def test_image_open_and_resize(tmp_path: Path):
    path = tmp_path / "photo.jpg"
    Image.new("RGB", (2000, 1000), "white").save(path)
    img = open_source_image(path)
    small = fit_long_edge(img, 400)
    assert max(small.size) == 400


def test_atomic_processing_does_not_modify_original(tmp_path: Path):
    original = tmp_path / "ORIGINAL" / "photo.jpg"
    finished = tmp_path / "FINISHED" / "photo.jpg"
    original.parent.mkdir()
    Image.new("RGB", (80, 80), "white").save(original, "JPEG", quality=95)
    before = sha256_file(original)

    img = Image.new("RGB", (80, 80), "black")
    save_jpeg_atomic(img, finished, 90)

    assert finished.exists()
    assert sha256_file(original) == before


def test_unique_path_prevents_original_overwrite(tmp_path: Path):
    original_dir = tmp_path / "ORIGINAL"
    original_dir.mkdir()
    first = original_dir / "same.jpg"
    second_source = tmp_path / "incoming_same.jpg"
    Image.new("RGB", (20, 20), "white").save(first)
    Image.new("RGB", (20, 20), "black").save(second_source)
    first_checksum = sha256_file(first)

    dest = unique_path(first)
    atomic_copy(second_source, dest)

    assert dest.name == "same_0001.jpg"
    assert sha256_file(first) == first_checksum
    assert sha256_file(dest) != first_checksum


def test_processing_corrections_keep_color_and_change_tone():
    img = Image.new("RGB", (80, 80), (88, 78, 62))
    corrected = apply_natural_corrections(
        img,
        {
            "auto_exposure": True,
            "auto_white_balance": True,
            "highlight_recovery": True,
            "shadow_recovery": True,
            "sharpening": True,
        },
    )
    assert corrected.mode == "RGB"
    assert corrected.getpixel((20, 20)) != img.getpixel((20, 20))
    assert len(set(corrected.getpixel((20, 20)))) > 1


def test_processing_corrections_do_not_darken_normal_event_photo():
    img = Image.new("RGB", (160, 100), (144, 137, 132))
    corrected = apply_natural_corrections(
        img,
        {
            "auto_exposure": True,
            "auto_white_balance": True,
            "highlight_recovery": True,
            "shadow_recovery": True,
            "face_aware_brightness": False,
            "noise_reduction": False,
            "sharpening": False,
        },
    )
    before = ImageStat.Stat(img.convert("L")).mean[0]
    after = ImageStat.Stat(corrected.convert("L")).mean[0]
    assert after >= before - 3


def test_face_aware_correction_never_darkens_scene():
    img = Image.new("RGB", (160, 100), (155, 148, 140))
    corrected = apply_natural_corrections(
        img,
        {
            "auto_exposure": False,
            "auto_white_balance": False,
            "highlight_recovery": False,
            "shadow_recovery": False,
            "face_aware_brightness": True,
            "noise_reduction": False,
            "sharpening": False,
        },
    )
    before = ImageStat.Stat(img.convert("L")).mean[0]
    after = ImageStat.Stat(corrected.convert("L")).mean[0]
    assert after >= before - 1


def test_admin_pin_session_is_signed(monkeypatch):
    monkeypatch.setenv("ADMIN_PIN", "824026")
    token = make_session()
    assert valid_session(token)
    assert not valid_session(token + "x")
