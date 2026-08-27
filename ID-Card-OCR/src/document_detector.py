"""Keyword and pattern based document classification."""

from __future__ import annotations

import re


DOCUMENT_TYPES = ("Aadhaar", "PAN", "Driving Licence", "Voter ID", "Unknown")


def _has(text: str, pattern: str) -> bool:
    return bool(re.search(pattern, text, re.IGNORECASE))


def detect_document_type(text: str) -> dict[str, str]:
    """Classify OCR text using multiple document-specific signals.

    A single vague keyword such as ``DL`` cannot classify a card by itself.
    """
    text = text or ""
    scores = {name: 0 for name in DOCUMENT_TYPES[:-1]}

    for pattern, points in ((r"\b(?:aadhaar|aadhar)\b", 4), (r"\buidai\b", 4), (r"\b(?:aadhaar\s*(?:no|number)|vid)\b", 3), (r"\b\d{4}\s*\d{4}\s*\d{4}\b", 2)):
        if _has(text, pattern):
            scores["Aadhaar"] += points
    for pattern, points in (
        (r"income\s+tax(?:\s+department)?", 4),
        (r"permanent\s+account(?:\s+(?:number|no))?", 5),
        (r"\bpan\b", 2),
        # PAN's 5 letters + 4 digits + letter format is a strong signal even
        # when a card header is cropped or OCR misses the word "PAN".
        (r"\b[A-Z]{5}\s*\d{4}\s*[A-Z]\b", 4),
    ):
        if _has(text, pattern):
            scores["PAN"] += points
    for pattern, points in (
        (r"driving\s+licen[cs]e", 6),
        (r"transport\s+department", 3),
        (r"\b(?:dl|d\.l\.)\s*(?:no|number)?\b", 1),
        (r"valid\s+(?:till|upto|from)", 2),
        # Covers common DL-1420110012345 and state-code variants.
        (r"\b(?:[A-Z]{2}|DL)[\s-]*\d{2,4}[\s-]*\d{4}[\s-]*\d{4,7}\b", 3),
    ):
        if _has(text, pattern):
            scores["Driving Licence"] += points
    for pattern, points in ((r"election\s+commission", 5), (r"\bepic\b", 4), (r"elector(?:al)?", 3), (r"voter(?:'s)?\s*(?:id|identity)", 4)):
        if _has(text, pattern):
            scores["Voter ID"] += points

    document_type, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score < 3:
        document_type = "Unknown"
    return {"document_type": document_type}
