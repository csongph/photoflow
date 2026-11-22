from __future__ import annotations
import json
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

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
    with Image.open(path) as source:
        rgba = source.convert("RGBA")
    if rgba.getchannel("A").getextrema()[0] < 255:
        # Flatten transparent cutouts before dropping alpha. PNG editors often
        # keep a checkerboard preview in the hidden RGB pixels; converting
        # straight to RGB would expose that checkerboard in the final photo.
        background = Image.new("RGBA", rgba.size, (0, 0, 0, 255))
        return Image.alpha_composite(background, rgba).convert("RGB")
    return rgba.convert("RGB")


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


def _frame_aperture(frame: Image.Image) -> tuple[int, int, int, int] | None:
    """Find the central transparent opening in a frame, conservatively."""
    alpha = frame.getchannel("A")
    sample = alpha.copy()
    sample.thumbnail((256, 256), Image.Resampling.BILINEAR)
    width, height = sample.size
    values = list(sample.getdata())
    # Start from the most central transparent pixel. Four-way connectivity avoids
    # treating antialiased diagonal edges as a path into the decorative border.
    candidates = [
        (x, y) for y in range(max(0, height // 2 - height // 10), min(height, height // 2 + height // 10 + 1))
        for x in range(max(0, width // 2 - width // 10), min(width, width // 2 + width // 10 + 1))
        if values[y * width + x] < 40
    ]
    if not candidates:
        return None
    sx, sy = min(candidates, key=lambda point: (point[0] - width / 2) ** 2 + (point[1] - height / 2) ** 2)
    # Find the largest clear rectangle containing the center seed. The bounding
    # box of a transparent opening can include side ghosts or ornaments; fitting
    # into an actually clear rectangle prevents those decorations covering a
    # person near the edge of the photo.
    row_spans: list[tuple[int, int] | None] = []
    for y in range(height):
        if values[y * width + sx] >= 40:
            row_spans.append(None)
            continue
        left = sx
        right = sx + 1
        while left > 0 and values[y * width + left - 1] < 40:
            left -= 1
        while right < width and values[y * width + right] < 40:
            right += 1
        row_spans.append((left, right))
    best_area = 0
    best_box = None
    for top in range(sy, -1, -1):
        if row_spans[top] is None:
            break
        clear_left, clear_right = row_spans[top]
        for bottom in range(sy, height):
            span = row_spans[bottom]
            if span is None:
                break
            clear_left = max(clear_left, span[0])
            clear_right = min(clear_right, span[1])
            area = (clear_right - clear_left) * (bottom - top + 1)
            if area > best_area:
                best_area = area
                best_box = (clear_left, top, clear_right, bottom + 1)
    if best_box is None:
        return None
    min_x, min_y, max_x, max_y = best_box
    # Convert the safe opening rectangle to source resolution and inset from
    # antialiased edges for a small additional safety margin.
    sx_scale, sy_scale = frame.width / width, frame.height / height
    inset_x, inset_y = max(2, round((max_x - min_x + 1) * sx_scale * .025)), max(2, round((max_y - min_y + 1) * sy_scale * .025))
    box = (
        max(0, round(min_x * sx_scale) + inset_x),
        max(0, round(min_y * sy_scale) + inset_y),
        min(frame.width, round((max_x + 1) * sx_scale) - inset_x),
        min(frame.height, round((max_y + 1) * sy_scale) - inset_y),
    )
    return box if box[2] - box[0] >= frame.width * .3 and box[3] - box[1] >= frame.height * .3 else None


def _detect_photo_faces(img: Image.Image) -> list[tuple[int, int, int, int]]:
    """Detect faces locally; coordinates are returned in the source photo."""
    try:
        import cv2
        import numpy as np

        rgb = np.asarray(img.convert("RGB"))
        scale = min(1.0, 1000 / max(img.size))
        if scale < 1:
            rgb = cv2.resize(rgb, (max(1, round(img.width * scale)), max(1, round(img.height * scale))))
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(20, 20))
        return [tuple(round(value / scale) for value in face) for face in faces]
    except Exception:
        return []


def _face_safe_crop(img: Image.Image, target_aspect: float, faces: list[tuple[int, int, int, int]]) -> Image.Image | None:
    """Fill a frame opening while keeping detected heads and breathing room visible."""
    if not faces or target_aspect <= 0:
        return None
    width, height = img.size
    source_aspect = width / height
    if abs(source_aspect - target_aspect) < .015:
        return img.copy()
    face_left = min(x for x, _, _, _ in faces)
    face_top = min(y for _, y, _, _ in faces)
    face_right = max(x + w for x, _, w, _ in faces)
    face_bottom = max(y + h for _, y, _, h in faces)
    face_size = max(1, round(sum(min(w, h) for _, _, w, h in faces) / len(faces)))
    if source_aspect > target_aspect:
        crop_width = max(1, round(height * target_aspect))
        margin = round(face_size * .45)
        low = max(0, face_right + margin - crop_width)
        high = min(width - crop_width, face_left - margin)
        if low > high:
            return None
        left = round(min(high, max(low, (width - crop_width) / 2)))
        return img.crop((left, 0, left + crop_width, height))
    crop_height = max(1, round(width / target_aspect))
    top_margin = round(face_size * .55)
    bottom_margin = round(face_size * 1.6)
    low = max(0, face_bottom + bottom_margin - crop_height)
    high = min(height - crop_height, face_top - top_margin)
    if low > high:
        return None
    top = round(min(high, max(low, (height - crop_height) / 2)))
    return img.crop((0, top, width, top + crop_height))


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
        if gallery.get("photobooth_frame_auto_orientation"):
            # New frame sets are orientation-aware: never crop a portrait design
            # into landscape (or vice versa) and silently damage the artwork.
            return img
        alternate = cache / f"photobooth-frame-{'portrait' if orientation == 'landscape' else 'landscape'}.png"
        legacy = cache / "photobooth-frame.png"
        frame_path = alternate if alternate.is_file() else legacy
    if not frame_path.is_file():
        raise RuntimeError(f"Photobooth {orientation} frame is enabled but no compatible PNG is available")
    with Image.open(frame_path) as source:
        frame = source.convert("RGBA")
    aperture = _frame_aperture(frame)
    if aperture is None:
        # Keep the source photo intact if a custom PNG has no clear central
        # aperture that can be safely detected.
        return img
    try:
        scale = min(1.35, max(0.7, float(gallery.get("photobooth_frame_scale", 1))))
        offset_x = min(0.15, max(-0.15, float(gallery.get("photobooth_frame_x", 0))))
        offset_y = min(0.15, max(-0.15, float(gallery.get("photobooth_frame_y", 0))))
    except (TypeError, ValueError):
        scale, offset_x, offset_y = 1, 0, 0
    # Use the full frame aspect ratio as the output canvas. This avoids cropping
    # its artwork to fit the camera's aspect ratio, which previously shifted the
    # transparent opening over people's faces and bodies.
    output_width = max(1, img.width if orientation == "landscape" else round(img.height * frame.width / frame.height))
    output_height = max(1, round(output_width * frame.height / frame.width))
    if orientation == "portrait":
        output_height = img.height
        output_width = max(1, round(output_height * frame.width / frame.height))
    # Apply optional admin adjustment to the frame but keep the artwork ratio.
    frame = frame.resize((max(1, round(output_width * scale)), max(1, round(output_height * scale))), Image.Resampling.LANCZOS)
    aperture = tuple(round(value * (output_width / (frame.width / scale))) for value in aperture)
    # Transform aperture with the same scale and translation as its frame.
    ax0, ay0, ax1, ay1 = aperture
    aperture = (
        round((ax0 - output_width / 2) * scale + output_width / 2 + output_width * offset_x),
        round((ay0 - output_height / 2) * scale + output_height / 2 + output_height * offset_y),
        round((ax1 - output_width / 2) * scale + output_width / 2 + output_width * offset_x),
        round((ay1 - output_height / 2) * scale + output_height / 2 + output_height * offset_y),
    )
    canvas = Image.new("RGBA", (output_width, output_height), (0, 0, 0, 0))
    x = (output_width - frame.width) // 2 + round(output_width * offset_x)
    y = (output_height - frame.height) // 2 + round(output_height * offset_y)
    left, top = max(0, x), max(0, y)
    right, bottom = min(output_width, x + frame.width), min(output_height, y + frame.height)
    if right > left and bottom > top:
        visible = frame.crop((left - x, top - y, right - x, bottom - y))
        canvas.alpha_composite(visible, (left, top))
    frame = canvas
    # Use a blurred, full-canvas version of the shot behind the frame. The sharp
    # photo fills the opening when a crop keeps all detected faces; groups that
    # cannot fit safely fall back to the complete uncropped photo.
    aperture = (max(0, aperture[0]), max(0, aperture[1]), min(output_width, aperture[2]), min(output_height, aperture[3]))
    if aperture[2] <= aperture[0] or aperture[3] <= aperture[1]:
        return img
    aw, ah = aperture[2] - aperture[0], aperture[3] - aperture[1]
    backdrop_size = (max(1, output_width // 4), max(1, output_height // 4))
    backdrop = ImageOps.fit(img.convert("RGB"), backdrop_size, method=Image.Resampling.LANCZOS)
    backdrop = backdrop.filter(ImageFilter.GaussianBlur(radius=max(2, round(min(backdrop_size) * .035))))
    if backdrop.size != (output_width, output_height):
        backdrop = backdrop.resize((output_width, output_height), Image.Resampling.BILINEAR)
    result = backdrop.convert("RGBA")
    source_photo = img.convert("RGB")
    safe_crop = _face_safe_crop(source_photo, aw / ah, _detect_photo_faces(source_photo))
    # When a face-safe crop can include every detected face, fill the opening
    # edge to edge. If a wide group cannot fit safely, show the whole photo with
    # the blurred fill behind it rather than cutting anyone out.
    fit = ImageOps.fit(safe_crop, (aw, ah), method=Image.Resampling.LANCZOS) if safe_crop else ImageOps.contain(source_photo, (aw, ah), method=Image.Resampling.LANCZOS)
    result.alpha_composite(fit.convert("RGBA"), (aperture[0] + (aw - fit.width) // 2, aperture[1] + (ah - fit.height) // 2))
    result.alpha_composite(frame)
    return result.convert("RGB")


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
