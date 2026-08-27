"""Tests for multi-signal document type detection."""

from __future__ import annotations

import unittest

from src.document_detector import detect_document_type


class DocumentDetectorTests(unittest.TestCase):
    def test_aadhaar_detection(self):
        self.assertEqual(detect_document_type("Government of India UIDAI Aadhaar Number 1234 5678 9012")["document_type"], "Aadhaar")

    def test_pan_detection(self):
        self.assertEqual(detect_document_type("INCOME TAX DEPARTMENT Permanent Account Number ABCDE1234F")["document_type"], "PAN")

    def test_pan_number_without_header_is_still_detected(self):
        self.assertEqual(detect_document_type("ABCDE1234F")["document_type"], "PAN")

    def test_driving_licence_detection(self):
        self.assertEqual(detect_document_type("DRIVING LICENCE Transport Department Valid Till")["document_type"], "Driving Licence")

    def test_voter_id_detection(self):
        self.assertEqual(detect_document_type("Election Commission of India EPIC Number ABC1234567")["document_type"], "Voter ID")

    def test_unknown_when_evidence_is_insufficient(self):
        self.assertEqual(detect_document_type("A small card with a date")["document_type"], "Unknown")


if __name__ == "__main__":
    unittest.main()
