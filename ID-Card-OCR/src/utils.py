"""Small shared helpers and privacy-safe output utilities."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any


NOT_DETECTED = "Not detected"


def value_or_not_detected(value: str | None) -> str:
    """Return the public placeholder for missing or empty values."""
    return value.strip() if isinstance(value, str) and value.strip() else NOT_DETECTED


def compact_digits(value: str) -> str:
    """Return only digits, useful only after a field-specific match."""
    return re.sub(r"\D", "", value)


def normalise_ocr_digits(value: str) -> str:
    """Conservatively repair common OCR digit substitutions in numeric fields."""
    return value.translate(str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "|": "1"}))


def format_aadhaar(value: str) -> str:
    digits = compact_digits(value)
    return f"{digits[:4]} {digits[4:8]} {digits[8:12]}" if len(digits) == 12 else value


def mask_aadhaar(value: str) -> str:
    """Mask all but the final four digits before a value reaches the UI/API."""
    digits = compact_digits(value)
    return f"XXXX XXXX {digits[-4:]}" if len(digits) == 12 else NOT_DETECTED


def mask_pan(value: str) -> str:
    """Mask a 10-character PAN while retaining only its last five characters."""
    compact = re.sub(r"[^A-Za-z0-9]", "", value).upper()
    return f"XXXXX{compact[-5:]}" if len(compact) == 10 else NOT_DETECTED


def mask_driving_licence(value: str) -> str:
    """Mask a licence number while retaining its final four characters."""
    compact = re.sub(r"[^A-Za-z0-9]", "", value).upper()
    if len(compact) < 8:
        return NOT_DETECTED
    hidden = max(4, len(compact) - 4)
    return f"{'X' * hidden}{compact[-4:]}"


def is_valid_date(value: str) -> bool:
    """Validate a human birth date, rejecting future and implausibly old dates."""
    try:
        parsed = datetime.strptime(value.replace("-", "/").replace(".", "/"), "%d/%m/%Y").date()
    except ValueError:
        return False
    today = date.today()
    return date(today.year - 125, 1, 1) <= parsed <= today


def clean_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Ensure the public response never contains blank strings or None values."""
    return {key: value_or_not_detected(value) if value is None or isinstance(value, str) else value for key, value in data.items()}
