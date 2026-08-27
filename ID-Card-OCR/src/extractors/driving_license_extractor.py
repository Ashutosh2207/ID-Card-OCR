"""Tolerant driving licence extraction across Indian state formats."""

from __future__ import annotations

import re

from .base_extractor import BaseExtractor
from ..utils import NOT_DETECTED


class DrivingLicenceExtractor(BaseExtractor):
    document_type = "Driving Licence"

    def extract_licence_number(self, text: str) -> str:
        """Extract state-code and compact Indian driving-licence formats."""
        patterns = (
            re.compile(r"\b([A-Z]{2}\s*[- ]?\s*\d{2}\s*[- ]?\s*\d{4}\s*[- ]?\s*\d{4,7})\b", re.I),
            re.compile(r"\b(DL\s*[- ]?\s*\d{2,4}\s*[- ]?\s*\d{4,7}\s*[- ]?\s*\d{4,7})\b", re.I),
        )
        for line in self.lines(text):
            # Keep state letters untouched.  Digit substitution is deliberately
            # not applied globally because codes such as Odisha's "OD" are valid.
            candidate_line = line.upper()
            for pattern in patterns:
                match = pattern.search(candidate_line)
                if match:
                    return re.sub(r"\s*[- ]\s*", "-", match.group(1)).upper()
        return NOT_DETECTED

    def extract_validity(self, text: str) -> str:
        value = self.extract_labeled_value(text, r"valid\s*(?:till|upto|up\s*to|from)")
        if value != NOT_DETECTED:
            date_match = re.search(r"\d{2}\s*[/.\-]\s*\d{2}\s*[/.\-]\s*\d{4}", value)
            return re.sub(r"\s+", "", date_match.group(0)) if date_match else value
        matches = re.findall(r"\b\d{2}\s*[/.\-]\s*\d{2}\s*[/.\-]\s*\d{4}\b", text)
        return re.sub(r"\s+", "", matches[-1]) if len(matches) >= 2 else NOT_DETECTED

    def extract_vehicle_class(self, text: str) -> str:
        value = self.extract_labeled_value(text, r"(?:class(?:\s+of)?\s+vehicle|vehicle\s+class|category)")
        if value != NOT_DETECTED:
            return value
        match = re.search(r"\b(?:MCWG|MCWOG|LMV|HMV|TRANS(?:PORT)?)\b", text, re.I)
        return match.group(0).upper() if match else NOT_DETECTED

    def extract(self, text: str) -> dict[str, str]:
        return {
            "document_type": self.document_type,
            "name": self.extract_name(text),
            "date_of_birth": self.extract_date_of_birth(text),
            "id_number": self.extract_licence_number(text),
            "address": self.extract_address(text),
            "validity": self.extract_validity(text),
            "vehicle_class": self.extract_vehicle_class(text),
        }
