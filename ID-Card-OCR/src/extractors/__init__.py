"""Document-specific extractor implementations and factory."""

from __future__ import annotations

from .aadhaar_extractor import AadhaarExtractor
from .base_extractor import BaseExtractor
from .driving_license_extractor import DrivingLicenceExtractor
from .pan_extractor import PANExtractor
from .voter_id_extractor import VoterIDExtractor


def get_extractor(document_type: str) -> BaseExtractor:
    """Return the appropriate extractor, using the safe generic fallback if needed."""
    extractors: dict[str, BaseExtractor] = {
        "Aadhaar": AadhaarExtractor(),
        "PAN": PANExtractor(),
        "Driving Licence": DrivingLicenceExtractor(),
        "Voter ID": VoterIDExtractor(),
    }
    return extractors.get(document_type, BaseExtractor())


__all__ = ["BaseExtractor", "AadhaarExtractor", "PANExtractor", "DrivingLicenceExtractor", "VoterIDExtractor", "get_extractor"]
