from __future__ import annotations

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

try:
    import cv2
except Exception:  # pragma: no cover - OpenCV is optional for face-aware correction.
    cv2 = None


def auto_white_balance(img: Image.Image) -> Image.Image:
    arr = np.asarray(img.convert("RGB")).astype(np.float32)
    sample = arr.reshape(-1, 3)
    brightness = sample.mean(axis=1)
    usable = sample[(brightness > 8) & (brightness < 247)]
    if usable.size == 0:
        usable = sample
    avg = usable.mean(axis=0)
    gray = avg.mean()
    scale = np.clip(gray / np.maximum(avg, 1), 0.86, 1.16)
    arr = np.clip(arr * scale, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def auto_exposure(img: Image.Image) -> Image.Image:
    lum = np.asarray(ImageOps.grayscale(img)).astype(np.float32)
    mean = np.asarray(ImageOps.grayscale(img)).mean()
    if mean <= 1:
        return img
    p2, p98 = np.percentile(lum, [2, 98])
    target_mean = 142 if p98 < 248 else 136
    min_factor = 1.0 if mean < 150 else 0.96
    factor = float(np.clip(target_mean / mean, min_factor, 1.18))
    img = ImageEnhance.Brightness(img).enhance(factor)
    if p98 - p2 < 150:
        img = ImageEnhance.Contrast(img).enhance(1.035)
    return img


def recover_highlights_shadows(img: Image.Image, highlight: float, shadow: float) -> Image.Image:
    arr = np.asarray(img.convert("RGB")).astype(np.float32)
    if shadow:
        mask = np.clip((118 - arr.mean(axis=2)) / 118, 0, 1)[..., None]
        arr += mask * shadow * 1.35
    if highlight:
        mask = np.clip((arr.mean(axis=2) - 162) / 93, 0, 1)[..., None]
        arr += mask * highlight * 1.05
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def face_aware_brightness(img: Image.Image) -> Image.Image:
    try:
        if cv2 is None:
            return img
        arr = cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2GRAY)
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        faces = cascade.detectMultiScale(arr, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
        if len(faces) == 0:
            return img
        samples = []
        rgb = np.asarray(img.convert("RGB"))
        for x, y, w, h in faces[:5]:
            samples.append(rgb[y : y + h, x : x + w].mean())
        mean = float(np.mean(samples))
        factor = float(np.clip(135 / max(mean, 1), 1.0, 1.14))
        return ImageEnhance.Brightness(img).enhance(factor)
    except Exception:
        return img


def apply_natural_corrections(img: Image.Image, options: dict) -> Image.Image:
    img = img.convert("RGB")
    if options.get("auto_white_balance", True):
        img = auto_white_balance(img)
    if options.get("auto_exposure", True):
        img = auto_exposure(img)
    if options.get("face_aware_brightness", False):
        img = face_aware_brightness(img)
    if options.get("highlight_recovery", True) or options.get("shadow_recovery", True):
        img = recover_highlights_shadows(img, -7 if options.get("highlight_recovery", True) else 0, 6 if options.get("shadow_recovery", True) else 0)
    if options.get("noise_reduction", False):
        img = img.filter(ImageFilter.MedianFilter(size=3))
    if options.get("sharpening", True):
        img = img.filter(ImageFilter.UnsharpMask(radius=1.1, percent=70, threshold=4))
    return img
