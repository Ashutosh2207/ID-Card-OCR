"""Voter ID / EPIC extraction."""

from __future__ import annotations

import re

from .base_extractor import BaseExtractor, RELATION_PATTERN
from ..text_cleaner import clean_name
from ..utils import NOT_DETECTED


class VoterIDExtractor(BaseExtractor):
    document_type = "Voter ID"

    def extract_epic_number(self, text: str) -> str:
        """Extract the standard three-letter, seven-digit EPIC number."""
        labelled = re.search(r"\b(?:epic|elector(?:'s)?\s*(?:photo\s*)?identity\s*(?:card|no|number)?)\b[^A-Z0-9]{0,12}([A-Z]{3}\s*\d{7})\b", text, re.I)
        if labelled:
            return re.sub(r"\s+", "", labelled.group(1)).upper()
        match = re.search(r"\b([A-Z]{3}\s*\d{7})\b", text, re.I)
        return re.sub(r"\s+", "", match.group(1)).upper() if match else NOT_DETECTED

    def extract_relation_name(self, text: str) -> str:
        lines = self.lines(text)
        for index, line in enumerate(lines):
            if re.search(r"\b(?:father|husband|mother|relation)\b", line, re.I) or RELATION_PATTERN.search(line):
                value = re.sub(r"^.*?(?:father(?:'s)?\s*name|husband(?:'s)?\s*name|mother(?:'s)?\s*name|S\s*/\s*O|D\s*/\s*O|W\s*/\s*O)\s*[:\-]?", "", line, flags=re.I)
                if self._valid_name(value):
                    return clean_name(value)
                if index + 1 < len(lines) and self._valid_name(lines[index + 1]):
                    return clean_name(lines[index + 1])
        return NOT_DETECTED

    def extract_age(self, text: str) -> str:
        match = re.search(r"\bage\s*[:\-]?\s*(\d{1,3})\b", text, re.I)
        if match and 0 < int(match.group(1)) < 125:
            return match.group(1)
        return NOT_DETECTED

    def extract(self, text: str) -> dict[str, str]:
        dob = self.extract_date_of_birth(text)
        return {
            "document_type": self.document_type,
            "name": self.extract_name(text),
            "father_or_husband_name": self.extract_relation_name(text),
            "date_of_birth": dob,
            "age": self.extract_age(text),
            "gender": self.extract_gender(text),
            "id_number": self.extract_epic_number(text),
            "address": self.extract_address(text),
        }
