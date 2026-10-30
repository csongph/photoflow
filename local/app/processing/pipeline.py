from __future__ import annotations
import json
from pathlib import Path

from PIL import Image, ImageOps

from ..config import settings
from ..models import Event, Photo
from ..utils.files import IMAGE_EXTENSIONS, is_raw


class UnsupportedRawError(RuntimeError):
    pass


def open_source_image(path: Path) -> Image.Image:
    if is_raw(path):
        try:
            import rawpy  # type: ignore

            with rawpy.imread(str(path)) as raw:
                rgb = raw.postprocess()
            return Image.fromarray(rgb)
        except Exception as exc:
            raise UnsupportedRawError(f"Unsupported RAW file: {exc}") from exc
    if path.suffix.lower() not in IMAGE_EXTENSIONS:
        raise UnsupportedRawError("Unsupported file type")
    return Image.open(path).convert("RGB")


def fit_long_edge(img: Image.Image, long_edge: int) -> Image.Image:
    width, height = img.size
    scale = long_edge / max(width, height)
    if scale >= 1:
        return img.copy()
    return img.resize((int(width * scale), int(height * scale)), Image.Resampling.LANCZOS)


def save_jpeg_atomic(img: Image.Image, path: Path, quality: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".processing.tmp")
    img.save(tmp, "JPEG", quality=quality, optimize=True)
    tmp.replace(path)


def apply_photobooth_frame(img: Image.Image, event: Event) -> Image.Image:
    try:
        gallery = json.loads(event.gallery_json or "{}")
    except json.JSONDecodeError:
        gallery = {}
    if not gallery.get("photobooth_frame_enabled"):
        return img

    orientation = "landscape" if img.width >= img.height else "portrait"
    cache = Path(event.root_path) / "CACHE"
    frame_path = cache / f"photobooth-frame-{orientation}.png"
    if not frame_path.is_file():
        alternate = cache / f"photobooth-frame-{'portrait' if orientation == 'landscape' else 'landscape'}.png"
        legacy = cache / "photobooth-frame.png"
        frame_path = alternate if alternate.is_file() else legacy
    if not frame_path.is_file():
        raise RuntimeError(f"Photobooth {orientation} frame is enabled but no compatible PNG is available")
    with Image.open(frame_path) as source:
        frame = source.convert("RGBA")
    # Keep the PNG's proportions, then allow small framing adjustments so its
    # transparent opening can be aligned with the subject in the photograph.
    frame = ImageOps.contain(frame, img.size, method=Image.Resampling.LANCZOS)
    try:
        scale = min(1.35, max(0.7, float(gallery.get("photobooth_frame_scale", 1))))
        offset_x = min(0.15, max(-0.15, float(gallery.get("photobooth_frame_x", 0))))
        offset_y = min(0.15, max(-0.15, float(gallery.get("photobooth_frame_y", 0))))
    except (TypeError, ValueError):
        scale, offset_x, offset_y = 1, 0, 0
    frame = frame.resize((max(1, round(frame.width * scale)), max(1, round(frame.height * scale))), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", img.size, (0, 0, 0, 0))
    x = (img.width - frame.width) // 2 + round(img.width * offset_x)
    y = (img.height - frame.height) // 2 + round(img.height * offset_y)
    left, top = max(0, x), max(0, y)
    right, bottom = min(img.width, x + frame.width), min(img.height, y + frame.height)
    if right > left and bottom > top:
        visible = frame.crop((left - x, top - y, right - x, bottom - y))
        canvas.alpha_composite(visible, (left, top))
    frame = canvas
    return Image.alpha_composite(img.convert("RGBA"), frame).convert("RGB")


def process_photo(db, event: Event, photo: Photo) -> None:
    source = Path(photo.original_path)
    img = open_source_image(source)
    img = ImageOps.exif_transpose(img)
    img = apply_photobooth_frame(img, event)

    event_root = Path(event.root_path)
    base = Path(photo.filename).stem
    finished = event_root / "FINISHED" / f"{base}.jpg"
    preview = event_root / "PREVIEWS" / f"{base}.jpg"
    thumb = event_root / "THUMBNAILS" / f"{base}.jpg"

    save_jpeg_atomic(img, finished, settings.jpeg_quality)
    save_jpeg_atomic(fit_long_edge(img, 1600), preview, 86)
    save_jpeg_atomic(fit_long_edge(img, 400), thumb, 82)

    photo.finished_path = str(finished)
    photo.preview_path = str(preview)
    photo.thumbnail_path = str(thumb)
    photo.status = "PROCESSED"
    photo.error = ""
    db.commit()
