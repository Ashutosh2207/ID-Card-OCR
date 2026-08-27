"""Shared, context-aware field extraction helpers."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import date

from ..text_cleaner import clean_address, clean_name, clean_text
from ..utils import NOT_DETECTED, compact_digits, is_valid_date, normalise_ocr_digits, value_or_not_detected


STOPWORDS = {
    "government", "india", "aadhaar", "aadhar", "authority", "identification", "address", "mobile",
    "number", "date", "birth", "male", "female", "uidai", "enrollment", "enrolment", "income",
    "tax", "department", "permanent", "account", "driving", "licence", "license", "election",
    "commission", "elector", "card", "valid", "signature", "issued", "unique", "identity",
}
RELATION_PATTERN = re.compile(r"\b(?:S\s*/\s*O|D\s*/\s*O|W\s*/\s*O|C\s*/\s*O|S/O|D/O|W/O|C/O)\b", re.I)


class BaseExtractor(ABC):
    """Base interface plus careful generic extractors for shared fields."""

    document_type = "Unknown"

    def lines(self, text: str) -> list[str]:
        return [line.strip() for line in clean_text(text).splitlines() if line.strip()]

    def _valid_name(self, candidate: str) -> bool:
        candidate = clean_name(candidate)
        words = candidate.split()
        if not 1 <= len(words) <= 5 or len(candidate) < 3 or len(candidate) > 50:
            return False
        if any(len(word) == 1 and word not in {"K", "R", "V", "S"} for word in words):
            return False
        lowered = {word.lower().strip(".") for word in words}
        return not bool(lowered & STOPWORDS) and all(re.fullmatch(r"[A-Za-z.']+", word) for word in words)

    def extract_name(self, text: str) -> str:
        """Score candidates using labels, relations and proximity to DOB/gender."""
        lines = self.lines(text)
        candidates: list[tuple[int, str, int]] = []
        anchors = [index for index, line in enumerate(lines) if re.search(r"\b(?:d[0o]b|date\s+of\s+birth|year\s+of\s+birth|yob|male|female)\b", line, re.I)]
        for index, line in enumerate(lines):
            source = re.sub(r"^\s*(?:name|cardholder\s*name)\s*[:\-]?\s*", "", line, flags=re.I)
            score = 0
            if source != line:
                score += 8
            if RELATION_PATTERN.search(line):
                before_relation = RELATION_PATTERN.split(line)[0].strip(" :-")
                if self._valid_name(before_relation):
                    candidates.append((score + 5, clean_name(before_relation), index))
                continue
            if not self._valid_name(source):
                continue
            if any(abs(index - anchor) <= 3 for anchor in anchors):
                score += 4
            if index < max(8, len(lines) // 2):
                score += 1
            if 2 <= len(source.split()) <= 4:
                score += 1
            candidates.append((score, clean_name(source), index))
        if not candidates:
            return NOT_DETECTED
        best_score, best_name, _ = max(candidates, key=lambda item: item[0])
        return best_name if best_score >= 4 else NOT_DETECTED

    def extract_date_of_birth(self, text: str) -> str:
        """Extract a labelled full DOB first; a labelled plausible YOB is a fallback."""
        lines = self.lines(text)
        date_pattern = re.compile(r"\b(\d{2}\s*[/.\-]\s*\d{2}\s*[/.\-]\s*\d{4})\b")
        year_pattern = re.compile(r"\b(19\d{2}|20[0-2]\d)\b")
        label_pattern = re.compile(r"\b(?:d[0o]b|date\s+of\s+birth|year\s+of\s+birth|yob)\b", re.I)
        for index, line in enumerate(lines):
            context = " ".join(lines[max(0, index - 1): index + 2])
            if not label_pattern.search(context):
                continue
            match = date_pattern.search(context)
            if match:
                value = re.sub(r"\s+", "", match.group(1)).replace("-", "/").replace(".", "/")
                if is_valid_date(value):
                    return value
            year_match = year_pattern.search(context)
            if year_match:
                year = int(year_match.group(1))
                if date.today().year - 125 <= year <= date.today().year:
                    return str(year)
        for line in lines:
            # An unlabelled date is accepted only when it is a valid human DOB.
            match = date_pattern.search(line)
            if match:
                value = re.sub(r"\s+", "", match.group(1)).replace("-", "/").replace(".", "/")
                if is_valid_date(value):
                    return value
        return NOT_DETECTED

    def extract_gender(self, text: str) -> str:
        """Use word boundaries so 'female' is never matched merely as 'male'."""
        female = re.search(r"(?<![A-Za-z])f(?:e|3)male(?![A-Za-z])", text, re.I)
        male = re.search(r"(?<![A-Za-z])male(?![A-Za-z])", text, re.I)
        if female:
            return "Female"
        if male:
            return "Male"
        return NOT_DETECTED

    def extract_mobile(self, text: str) -> str:
        """Find Indian 10-digit mobile numbers while rejecting 12-digit IDs and PINs."""
        for match in re.finditer(r"(?<!\d)(?:\+91[\s-]*)?([6-9](?:[\s-]*\d){9})(?!\d)", text):
            digits = compact_digits(match.group(1))
            surrounding = text[max(0, match.start() - 18):match.end() + 18]
            if len(digits) == 10 and not re.search(r"\b(?:aadhaar|vid|pin)\b", surrounding, re.I):
                return digits
        return NOT_DETECTED

    def _is_address_stop(self, line: str) -> bool:
        return bool(re.search(
            r"\b(?:uidai|www\.|https?://|help(?:line)?|toll\s*free|enrol(?:ment)?|vid\b|qr\s*code|"
            r"dob|date\s+of\s+birth|gender|male|female|income\s+tax|driving\s+licen[cs]e|"
            r"election\s+commission|permanent\s+account)\b",
            line,
            re.I,
        )) or bool(re.search(r"\b\d{4}\s*\d{4}\s*\d{4}\b", line))

    def _is_useful_address_line(self, line: str) -> bool:
        """Reject OCR noise while retaining ordinary Indian address components."""
        letters = len(re.findall(r"[A-Za-z]", line))
        strange = len(re.findall(r"[^A-Za-z0-9,./#&()'\-: ]", line))
        if letters < 2 or strange > max(2, len(line) // 8):
            return False
        return not bool(re.fullmatch(r"[\d\s,./#\-]+", line))

    def extract_address(self, text: str) -> str:
        """Collect address-like lines from address/relationship context until a footer."""
        lines = self.lines(text)
        starts = [i for i, line in enumerate(lines) if re.search(r"\b(?:address|resident(?:ial)?\s+address)\b", line, re.I)]
        # Aadhaar commonly starts its printed address with D/O, S/O, W/O or C/O.
        # Only use that fallback when it resembles an address context, not a random
        # relationship field elsewhere on a card.
        if not starts:
            starts = [i for i, line in enumerate(lines) if RELATION_PATTERN.search(line) and (
                i + 1 < len(lines) and (bool(re.search(r"\d|\b(?:village|ward|street|road|nagar|district|pin)\b", lines[i + 1], re.I)))
            )]
        if not starts:
            return NOT_DETECTED
        collected: list[str] = []
        for line in lines[starts[0]: starts[0] + 7]:
            if self._is_address_stop(line):
                break
            line = re.sub(r"^\s*address\s*[:\-]?\s*", "", line, flags=re.I)
            # OCR may prepend a wrongly read Hindi "पता" before D/O, S/O, etc.
            # The relation marker is the trustworthy start of that address line.
            relation_match = RELATION_PATTERN.search(line)
            if relation_match and relation_match.start() > 0:
                line = line[relation_match.start():]
            if self._is_useful_address_line(line) and not re.fullmatch(r"(?:address|resident\s+address)[:\-]?", line, re.I):
                collected.append(line)
                # Indian address blocks conventionally end at the six-digit PIN.
                # Stopping here keeps QR/footer artefacts out of the result.
                if re.search(r"\b\d{6}\b", line):
                    break
        address = clean_address(", ".join(collected))
        if len(address) < 8 or not re.search(r"[A-Za-z]", address):
            return NOT_DETECTED
        return address

    def extract_labeled_value(self, text: str, labels: str, max_following_lines: int = 1) -> str:
        """Read a value on the same line as a label or immediately following it."""
        lines = self.lines(text)
        pattern = re.compile(rf"\b(?:{labels})\b\s*[:\-]?\s*(.*)$", re.I)
        for index, line in enumerate(lines):
            match = pattern.search(line)
            if not match:
                continue
            candidate = match.group(1).strip()
            if candidate:
                return candidate
            for following in lines[index + 1:index + 1 + max_following_lines]:
                if following:
                    return following
        return NOT_DETECTED

    def extract(self, text: str) -> dict[str, str]:
        """Safe fallback used when a document cannot be classified confidently."""
        return {
            "document_type": self.document_type,
            "name": self.extract_name(text),
            "date_of_birth": self.extract_date_of_birth(text),
            "gender": self.extract_gender(text),
            "mobile": self.extract_mobile(text),
            "id_number": NOT_DETECTED,
            "address": self.extract_address(text),
        }
