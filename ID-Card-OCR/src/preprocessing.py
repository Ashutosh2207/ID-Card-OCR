"""Image preparation helpers used before Tesseract OCR."""

from __future__ import annotations

import math
from typing import Iterable

import cv2
import numpy as np
from PIL import Image


def image_to_bgr(image: Image.Image | np.ndarray) -> np.ndarray:
    """Convert a Pillow image or ndarray into a safe, 3-channel BGR image."""
    if isinstance(image, Image.Image):
        rgb = np.asarray(image.convert("RGB"))
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    if not isinstance(image, np.ndarray) or image.size == 0:
        raise ValueError("A non-empty image is required.")
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    return image.copy()


def bgr_to_pil(image: np.ndarray) -> Image.Image:
    """Convert an OpenCV BGR image to a Pillow RGB image for pytesseract."""
    if image.ndim == 2:
        return Image.fromarray(image)
    return Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))


def _qr_points(image: np.ndarray) -> list[np.ndarray]:
    detector = cv2.QRCodeDetector()
    points_found: list[np.ndarray] = []
    try:
        multi_result = detector.detectAndDecodeMulti(image)
        if len(multi_result) == 4:
            ok, _decoded, points, _ = multi_result
            if ok and points is not None:
                points_found.extend(np.asarray(points))
    except (AttributeError, cv2.error, ValueError):
        pass
    if not points_found:
        try:
            _decoded, points, _ = detector.detectAndDecode(image)
            if points is not None:
                points_found.append(np.asarray(points)[0])
        except cv2.error:
            pass
    return points_found


def remove_qr_code(image: np.ndarray, return_coordinates: bool = False):
    """Mask detected QR polygons while leaving nearby text untouched.

    The mask is enlarged by only three percent to cover QR finder patterns, not a
    broad rectangular region.  ``return_coordinates=True`` is useful for tests
    and diagnostics; the default return value is simply the cleaned image.
    """
    result = image.copy()
    masked_regions: list[list[list[int]]] = []
    height, width = result.shape[:2]
    for raw_points in _qr_points(result):
        points = np.asarray(raw_points, dtype=np.float32).reshape(-1, 2)
        centre = points.mean(axis=0)
        expanded = centre + (points - centre) * 1.03
        polygon = np.round(expanded).astype(np.int32)
        polygon[:, 0] = np.clip(polygon[:, 0], 0, width - 1)
        polygon[:, 1] = np.clip(polygon[:, 1], 0, height - 1)
        colour = 255 if result.ndim == 2 else (255, 255, 255)
        cv2.fillConvexPoly(result, polygon, colour)
        masked_regions.append(polygon.tolist())
    return (result, masked_regions) if return_coordinates else result


def upscale(image: np.ndarray, minimum_width: int = 1600) -> np.ndarray:
    """Upscale only small cards; very large source images are left intact."""
    height, width = image.shape[:2]
    if width >= minimum_width:
        return image.copy()
    scale = min(3.0, minimum_width / max(width, 1))
    return cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)


def deskew(gray: np.ndarray) -> np.ndarray:
    """Correct a modest text skew when it can be estimated reliably."""
    inverted = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(inverted > 0))
    if len(coords) < 100:
        return gray
    angle = cv2.minAreaRect(coords[:, ::-1].astype(np.float32))[-1]
    angle = -(90 + angle) if angle < -45 else -angle
    if not math.isfinite(angle) or abs(angle) < 0.3 or abs(angle) > 12:
        return gray
    height, width = gray.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    return cv2.warpAffine(gray, matrix, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def preprocess_image(image: np.ndarray) -> np.ndarray:
    """Create a conservative high-contrast grayscale OCR variant.

    This intentionally avoids unconditional binarisation.  Adaptive thresholding
    is used only on low-contrast photos, where it normally helps Tesseract.
    """
    source = upscale(image_to_bgr(image))
    gray = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)
    gray = deskew(gray)
    contrast = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    if gray.std() < 45:
        filtered = cv2.medianBlur(contrast, 3)
        return cv2.adaptiveThreshold(filtered, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 9)
    blurred = cv2.GaussianBlur(contrast, (0, 0), 1.0)
    return cv2.addWeighted(contrast, 1.35, blurred, -0.35, 0)


def build_ocr_variants(image: np.ndarray) -> Iterable[np.ndarray]:
    """Return a small set of complementary OCR inputs, not every possible filter."""
    original = image_to_bgr(image)
    yield original
    yield upscale(original)
    yield preprocess_image(original)
