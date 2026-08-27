"""PAN card field extraction and validation."""

from __future__ import annotations

import re

from .base_extractor import BaseExtractor
from ..text_cleaner import clean_name
from ..utils import NOT_DETECTED


class PANExtractor(BaseExtractor):
    document_type = "PAN"

    def extract_pan_number(self, text: str) -> str:
        """Accept PAN-format values only when context or card structure supports them."""
        for line in self.lines(text):
            compact = re.sub(r"[\s-]", "", line.upper())
            match = re.search(r"\b([A-Z]{5}\d{4}[A-Z])\b", compact)
            if not match:
                continue
            context = line.lower()
            # The format is strong; the first five letters have a conventional 4th
            # status character, which still gives useful validation on noisy OCR.
            value = match.group(1)
            if re.search(r"pan|permanent|income\s*tax", context) or value[3] in "PC HATFBJL G".replace(" ", ""):
                return value
        return NOT_DETECTED

    def _person_value(self, text: str, labels: str) -> str:
        candidate = self.extract_labeled_value(text, labels)
        return clean_name(candidate) if candidate != NOT_DETECTED and self._valid_name(candidate) else NOT_DETECTED

    def extract_pan_name(self, text: str, father: bool = False) -> str:
        father_label = r"father(?:'s|s)?\s*name"
        if father:
            labelled = self._person_value(text, father_label)
        else:
            labelled = NOT_DETECTED
            for line in self.lines(text):
                # Avoid treating the "Name" part of "Father's Name" as the owner.
                # OCR frequently removes the apostrophe: "Fathers Name".
                if re.search(father_label, line, re.I):
                    continue
                match = re.search(r"\bname\b\s*[:\-]?\s*(.*)$", line, re.I)
                if match and self._valid_name(match.group(1)):
                    labelled = clean_name(match.group(1))
                    break
        if labelled != NOT_DETECTED:
            return labelled
        lines = self.lines(text)
        dob_index = next(
            (i for i, line in enumerate(lines) if re.search(r"\b(?:d[0o]b|date\s+of\s+birth)\b|\d{2}[/.\-]\d{2}[/.\-]\d{4}", line, re.I)),
            len(lines),
        )
        # A standard PAN face prints cardholder and father's name as the two
        # immediately preceding prominent lines before DOB, usually without
        # labels.  Prefer 2–5 word alphabetic lines; this rejects one-word OCR
        # fragments such as "SBS" and signature artefacts such as "Riot".
        candidates: list[tuple[int, str]] = []
        for index, line in enumerate(lines[:dob_index]):
            value = clean_name(line)
            words = value.split()
            if not self._valid_name(value) or not 2 <= len(words) <= 5:
                continue
            if any(len(word.replace(".", "")) < 2 for word in words):
                continue
            lowered = value.lower()
            if any(token in lowered for token in (
                "income", "department", "government", "india", "permanent", "account", "father", "fathers",
            )):
                continue
            score = 10
            # Lines near DOB are the two PAN identity names, not the top header.
            score += max(0, 8 - (dob_index - index))
            if value.isupper():
                score += 2
            candidates.append((score, value))
        names = [value for _score, value in sorted(candidates, key=lambda item: item[0], reverse=True)]
        # Preserve visual reading order: after filtering, the final two valid
        # lines before DOB are cardholder first, then father.
        ordered = [clean_name(line) for line in lines[:dob_index] if clean_name(line) in names]
        ordered = list(dict.fromkeys(ordered))
        if len(ordered) >= 2:
            return ordered[-1] if father else ordered[-2]
        return NOT_DETECTED

    def extract(self, text: str) -> dict[str, str]:
        return {
            "document_type": self.document_type,
            "name": self.extract_pan_name(text),
            "father_name": self.extract_pan_name(text, father=True),
            "date_of_birth": self.extract_date_of_birth(text),
            "id_number": self.extract_pan_number(text),
        }
