"""Aadhaar-specific contextual extraction."""

from __future__ import annotations

import re

from .base_extractor import BaseExtractor, RELATION_PATTERN
from ..text_cleaner import clean_name
from ..utils import NOT_DETECTED, compact_digits, format_aadhaar, normalise_ocr_digits


class AadhaarExtractor(BaseExtractor):
    document_type = "Aadhaar"

    def extract_name(self, text: str) -> str:
        """Prefer the cardholder name near DOB/gender, never a relation in address."""
        lines = self.lines(text)
        address_start = next(
            (i for i, line in enumerate(lines) if re.search(r"\baddress\b", line, re.I)),
            len(lines),
        )
        anchors = [
            i for i, line in enumerate(lines[:address_start])
            if re.search(r"\b(?:d[0o]b|date\s+of\s+birth|year\s+of\s+birth|yob|gender|male|female)\b", line, re.I)
        ]
        candidates: list[tuple[int, str]] = []
        for index, line in enumerate(lines[:address_start]):
            cleaned = re.sub(r"^\s*name\s*[:\-]?\s*", "", line, flags=re.I)
            # A bilingual Aadhaar often has Hindi and English on nearby rows.
            # Never allow a row containing a field label (for example noisy OCR
            # such as "'a Wea Fet DOB") to become a person's name.
            if re.search(
                r"\b(?:d[0o]b|date|birth|year|gender|male|female|mobile|number|address|uidai|vid)\b|\d",
                cleaned,
                re.I,
            ) or not self._valid_name(cleaned) or RELATION_PATTERN.search(line):
                continue
            words = clean_name(cleaned).split()
            # A name may be one word (e.g. Anjali), but OCR fragments such as
            # "'a" must not be accepted as a valid word.
            if any(len(re.sub(r"[^A-Za-z]", "", word)) < 2 for word in words):
                continue
            lowered = " ".join(words).lower()
            # Tesseract can merge "Government of India" with nearby Hindi text;
            # such a long synthetic token is not a person's name.
            if any(marker in lowered for marker in ("gov", "goven", "gover", "india", "indam", "uid")):
                continue
            if any(len(re.sub(r"[^A-Za-z]", "", word)) > 15 for word in words):
                continue
            score = 0
            if cleaned != line:
                score += 12
            # Aadhaar owner's name normally appears immediately before / close to
            # the DOB and gender row on the front side.
            if any(0 < anchor - index <= 3 for anchor in anchors):
                score += 8
            if 2 <= len(cleaned.split()) <= 4:
                score += 2
            candidates.append((score, clean_name(cleaned)))
        if not candidates:
            return NOT_DETECTED
        score, name = max(candidates, key=lambda item: item[0])
        return name if score >= 7 else NOT_DETECTED

    def extract_aadhaar_number(self, text: str) -> str:
        """Find the best 12-digit Aadhaar candidate without confusing a VID for it."""
        candidates: list[tuple[int, str]] = []
        pattern = re.compile(r"(?<!\d)(?:\d[\s-]*){12}(?!\d)")
        for line_index, line in enumerate(self.lines(text)):
            digit_ready = normalise_ocr_digits(line)
            for match in pattern.finditer(digit_ready):
                digits = compact_digits(match.group(0))
                if len(digits) != 12:
                    continue
                context_lines = self.lines(text)[max(0, line_index - 1):line_index + 2]
                context = " ".join(context_lines)
                if re.search(r"\bvid\b|virtual\s+id", context, re.I):
                    continue
                score = 1
                if re.search(r"\b(?:aadhaar|aadhar|uidai|uid)\b", context, re.I):
                    score += 5
                if re.search(r"\d{4}\s+\d{4}\s+\d{4}", match.group(0)):
                    score += 2
                if digits[0] in "23456789":
                    score += 1
                candidates.append((score, digits))
        if not candidates:
            return NOT_DETECTED
        score, value = max(candidates, key=lambda item: item[0])
        return format_aadhaar(value) if score >= 2 else NOT_DETECTED

    def extract(self, text: str) -> dict[str, str]:
        return {
            "document_type": self.document_type,
            "name": self.extract_name(text),
            "date_of_birth": self.extract_date_of_birth(text),
            "gender": self.extract_gender(text),
            "mobile": self.extract_mobile(text),
            "id_number": self.extract_aadhaar_number(text),
            "address": self.extract_address(text),
        }
