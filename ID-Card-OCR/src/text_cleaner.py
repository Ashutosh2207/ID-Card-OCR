"""Careful OCR text cleanup that preserves address punctuation and numbers."""

from __future__ import annotations

import re


def normalize_spaces(text: str) -> str:
    """Normalise line endings and horizontal whitespace without joining lines."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    return "\n".join(re.sub(r"[\t ]+", " ", line).strip() for line in text.split("\n"))


def clean_text(text: str) -> str:
    """Remove control characters and repeated blank lines from OCR output."""
    if not text:
        return ""
    text = "".join(char for char in text if char == "\n" or char >= " ")
    text = normalize_spaces(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_name(value: str) -> str:
    """Keep name-like letters, apostrophes, dots and spaces; do not guess letters."""
    value = re.sub(r"[^A-Za-z.' ]", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    return " ".join(part.capitalize() if part.islower() else part for part in value.split())


def clean_address(value: str) -> str:
    """Clean an address gently: slash, hyphen, commas, dots, digits and PIN stay."""
    value = value.replace("|", " ")
    value = re.sub(r"[^A-Za-z0-9,./#&()'\-: ]", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" ,;|-.")
    return value
