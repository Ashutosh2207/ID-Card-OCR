"""Tesseract integration with conservative multi-variant OCR selection."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytesseract
from pytesseract import Output

from config import get_settings
from .preprocessing import bgr_to_pil, build_ocr_variants, image_to_bgr
from .text_cleaner import clean_text


class OCRConfigurationError(RuntimeError):
    """Raised when the external Tesseract executable is unavailable."""


class OCRProcessingError(RuntimeError):
    """Raised when Tesseract cannot process a valid image."""


def configure_tesseract() -> None:
    """Apply the single configured executable path, if the user supplied one."""
    settings = get_settings()
    if settings.tesseract_path:
        path = Path(settings.tesseract_path)
        if not path.is_file():
            raise OCRConfigurationError(
                "Tesseract was not found at TESSERACT_PATH. Check .env or install Tesseract OCR."
            )
        pytesseract.pytesseract.tesseract_cmd = str(path)


def check_tesseract() -> str:
    """Return the detected Tesseract version or a helpful configuration error."""
    configure_tesseract()
    try:
        return str(pytesseract.get_tesseract_version())
    except pytesseract.TesseractNotFoundError as exc:
        raise OCRConfigurationError(
            "Tesseract OCR is not installed or is not on PATH. Set TESSERACT_PATH in .env."
        ) from exc


def _ocr_one(image: np.ndarray, psm: int) -> tuple[str, float]:
    settings = get_settings()
    options = f"--oem 3 --psm {psm}"
    try:
        pil_image = bgr_to_pil(image_to_bgr(image))
        details = pytesseract.image_to_data(
            pil_image, lang=settings.tesseract_language, config=options, output_type=Output.DICT
        )
        confidences = [float(item) for item in details.get("conf", []) if str(item) not in {"-1", ""}]
        text = pytesseract.image_to_string(pil_image, lang=settings.tesseract_language, config=options)
        return clean_text(text), (sum(confidences) / len(confidences) if confidences else 0.0)
    except pytesseract.TesseractNotFoundError as exc:
        raise OCRConfigurationError("Tesseract OCR is not installed or its configured path is invalid.") from exc
    except pytesseract.TesseractError as exc:
        raise OCRProcessingError("Tesseract could not read this image. Try a clearer image.") from exc


def _text_quality(text: str, confidence: float) -> float:
    """Favour reliable card fields over long, low-quality OCR garbage."""
    words = re.findall(r"[A-Za-z]{2,}", text)
    field_hits = len(re.findall(r"\b(?:DOB|Aadhaar|PAN|UIDAI|Licence|EPIC|Male|Female)\b", text, re.I))
    useful_digits = len(re.findall(r"\d{4,}", text))
    aadhaar_hits = len(re.findall(r"(?<!\d)(?:\d[\s-]*){12}(?!\d)", text))
    date_hits = len(re.findall(r"\b\d{2}[/.\-]\d{2}[/.\-]\d{4}\b", text))
    pan_hits = len(re.findall(r"\b[A-Z]{5}\s*\d{4}\s*[A-Z]\b", text, re.I))
    garbage = len(re.findall(r"[^\w\s,./:#&()'\-]", text))
    return (
        confidence
        + min(len(words), 35) * 0.35
        + field_hits * 4
        + useful_digits * 0.5
        + aadhaar_hits * 12
        + date_hits * 6
        + pan_hits * 10
        - garbage * 0.15
    )


def run_ocr_candidates(image: np.ndarray, include_variants: bool = True, limit: int = 6) -> list[str]:
    """Return the strongest distinct OCR reads for document-aware comparison.

    A PAN often has large, spaced name lines whereas an Aadhaar has denser text.
    Keeping a few ranked alternatives lets the extraction service choose the read
    that produces the most complete *validated* document fields, rather than
    trusting one global OCR score.
    """
    configure_tesseract()
    variants = build_ocr_variants(image) if include_variants else [image_to_bgr(image)]
    settings = get_settings()
    # PSM 6 works well for normal card blocks. PSM 11 is intentionally added for
    # sparse/front-and-back scans where a large white gap makes normal layout
    # analysis merge unrelated rows.
    page_segmentations = tuple(dict.fromkeys((settings.tesseract_psm, 11)))
    attempts: list[tuple[str, float]] = []
    for variant in variants:
        for psm in page_segmentations:
            text, confidence = _ocr_one(variant, psm)
            if text:
                attempts.append((text, _text_quality(text, confidence)))
    unique: list[str] = []
    for text, _score in sorted(attempts, key=lambda item: item[1], reverse=True):
        fingerprint = re.sub(r"\W+", "", text).lower()
        if fingerprint and all(fingerprint != re.sub(r"\W+", "", existing).lower() for existing in unique):
            unique.append(text)
        if len(unique) >= limit:
            break
    return unique


def run_ocr(image: np.ndarray, include_variants: bool = True) -> str:
    """Run OCR and return the single highest-ranked clean text for compatibility."""
    candidates = run_ocr_candidates(image, include_variants=include_variants, limit=1)
    return candidates[0] if candidates else ""
