"""One shared image-to-JSON pipeline for Streamlit and Flask."""

from __future__ import annotations

import io
from typing import Any

from PIL import Image, UnidentifiedImageError

from .document_detector import detect_document_type
from .extractors import get_extractor
from .ocr_engine import OCRConfigurationError, OCRProcessingError, run_ocr_candidates
from .preprocessing import image_to_bgr, remove_qr_code
from .utils import NOT_DETECTED, mask_aadhaar, mask_driving_licence, mask_pan


class ExtractionError(RuntimeError):
    """A safe, user-facing error raised for unusable uploads or OCR failures."""


def _mask_private_fields(data: dict[str, str], show_full_id: bool) -> dict[str, str]:
    result = data.copy()
    if show_full_id:
        return result
    document_type = result.get("document_type")
    if document_type == "Aadhaar":
        result["id_number"] = mask_aadhaar(result.get("id_number", ""))
    elif document_type == "PAN":
        result["id_number"] = mask_pan(result.get("id_number", ""))
    elif document_type == "Driving Licence":
        result["id_number"] = mask_driving_licence(result.get("id_number", ""))
    return result


def _extraction_quality(data: dict[str, str]) -> int:
    """Rank only validated populated fields; do not invent numeric confidence."""
    document_type = data.get("document_type", "Unknown")
    populated = sum(1 for value in data.values() if value != NOT_DETECTED)
    score = populated * 4
    if document_type == "PAN":
        # PAN identity is only complete when both distinct printed names are read.
        if data.get("id_number") != NOT_DETECTED:
            score += 8
        if data.get("name") != NOT_DETECTED:
            score += 5
        if data.get("father_name") != NOT_DETECTED:
            score += 5
        if data.get("name") == data.get("father_name"):
            score -= 10
    return score


def extract_from_image(image: Image.Image, show_full_id: bool = False) -> dict[str, Any]:
    """Execute QR removal, OCR, classification and document-specific extraction."""
    try:
        safe_image = remove_qr_code(image_to_bgr(image))
        ocr_candidates = run_ocr_candidates(safe_image)
    except (ValueError, UnidentifiedImageError) as exc:
        raise ExtractionError("The uploaded file is not a valid image.") from exc
    except (OCRConfigurationError, OCRProcessingError) as exc:
        raise ExtractionError(str(exc)) from exc
    if not ocr_candidates:
        raise ExtractionError("No text was detected. Try a clearer, well-lit image of the card.")
    extracted_candidates: list[tuple[int, dict[str, str], str]] = []
    for raw_text in ocr_candidates:
        document_type = detect_document_type(raw_text)["document_type"]
        data = get_extractor(document_type).extract(raw_text)
        data["document_type"] = document_type
        extracted_candidates.append((_extraction_quality(data), data, raw_text))
    _score, data, raw_text = max(extracted_candidates, key=lambda item: item[0])
    return {"status": "success", "data": _mask_private_fields(data, show_full_id), "raw_ocr_text": raw_text}


def extract_from_bytes(contents: bytes, show_full_id: bool = False) -> dict[str, Any]:
    """Decode in-memory upload bytes; images are never written to disk."""
    if not contents:
        raise ExtractionError("No image data was received.")
    try:
        with Image.open(io.BytesIO(contents)) as opened:
            image = opened.convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise ExtractionError("The uploaded file is corrupted or is not a supported image.") from exc
    return extract_from_image(image, show_full_id=show_full_id)
