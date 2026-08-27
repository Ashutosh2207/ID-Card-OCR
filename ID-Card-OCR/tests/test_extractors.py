"""Unit tests for field validation and document-specific extraction."""

from __future__ import annotations

import unittest

from src.extractors.aadhaar_extractor import AadhaarExtractor
from src.extractors.base_extractor import BaseExtractor
from src.extractors.pan_extractor import PANExtractor
from src.service import ExtractionError, extract_from_bytes
from src.utils import NOT_DETECTED, mask_driving_licence, mask_pan


class ExtractorTests(unittest.TestCase):
    def setUp(self):
        self.base = BaseExtractor()

    def test_aadhaar_number_is_formatted_and_vid_is_not_returned(self):
        text = "UIDAI\nAadhaar Number: 1234 5678 9012\nVID: 9999 8888 7777 6666"
        self.assertEqual(AadhaarExtractor().extract_aadhaar_number(text), "1234 5678 9012")

    def test_pan_extraction(self):
        text = "INCOME TAX DEPARTMENT\nName: RAHUL KUMAR\nFather's Name: RAMESH KUMAR\nDOB: 24/07/2003\nPAN: ABCDE1234F"
        data = PANExtractor().extract(text)
        self.assertEqual(data["id_number"], "ABCDE1234F")
        self.assertEqual(data["name"], "RAHUL KUMAR")
        self.assertEqual(data["father_name"], "RAMESH KUMAR")

    def test_pan_unlabelled_layout_uses_two_name_lines_before_dob(self):
        text = (
            "INCOME TAX DEPARTMENT\nGOVT. OF INDIA\nTWITTERPREET SINGH\n"
            "BALWINDER SINGH\n14/05/1995\nPermanent Account Number\nBWZPS1234R"
        )
        data = PANExtractor().extract(text)
        self.assertEqual(data["name"], "TWITTERPREET SINGH")
        self.assertEqual(data["father_name"], "BALWINDER SINGH")

    def test_pan_fathers_name_without_apostrophe_is_not_cardholder_name(self):
        text = (
            "INCOME TAX DEPARTMENT\nMax Smith\nFathers Name:\nSmith Branson\n"
            "07/08/1992\nAQWPS7772B"
        )
        data = PANExtractor().extract(text)
        self.assertEqual(data["name"], "Max Smith")
        self.assertEqual(data["father_name"], "Smith Branson")

    def test_labelled_date_and_year_of_birth(self):
        self.assertEqual(self.base.extract_date_of_birth("DOB: 24-07-2003"), "24/07/2003")
        self.assertEqual(self.base.extract_date_of_birth("Year of Birth: 2003"), "2003")
        self.assertEqual(self.base.extract_date_of_birth("Printed 2025"), NOT_DETECTED)

    def test_gender_respects_word_boundaries(self):
        self.assertEqual(self.base.extract_gender("Gender: Female"), "Female")
        self.assertEqual(self.base.extract_gender("Gender: Male"), "Male")

    def test_mobile_rejects_aadhaar_and_finds_indian_number(self):
        text = "Aadhaar: 1234 5678 9012\nMobile: 98765-43210\nPIN 110001"
        self.assertEqual(self.base.extract_mobile(text), "9876543210")

    def test_name_requires_context_and_rejects_headers(self):
        text = "Government of India\nName: Varun Kumar Gera\nDOB: 24/07/2003\nMale"
        self.assertEqual(self.base.extract_name(text), "Varun Kumar Gera")
        self.assertEqual(self.base.extract_name("Government of India\nUIDAI"), NOT_DETECTED)

    def test_aadhaar_name_does_not_use_relation_name_in_address(self):
        text = (
            "Government of India\nRAVI KUMAR\nDOB: 24/07/2003\nMale\n"
            "Address\nD/O Mukesh Kumar\nHouse No 12, Ashok Nagar, Delhi 110093\n"
            "UIDAI help@uidai.gov.in"
        )
        data = AadhaarExtractor().extract(text)
        self.assertEqual(data["name"], "RAVI KUMAR")
        self.assertIn("Ashok Nagar", data["address"])
        self.assertNotIn("UIDAI", data["address"])

    def test_aadhaar_name_rejects_bilingual_ocr_label_garbage(self):
        text = "'a Wea Fet DOB\nAnjali\nDOB: 18/09/1999\nFemale\nMobile No. 9582539507"
        self.assertEqual(AadhaarExtractor().extract_name(text), "Anjali")

    def test_aadhaar_name_rejects_merged_government_ocr_garbage(self):
        text = "MiGovenmentonindam Orere\nVarun Kumar Gera\nDOB: 24/07/2003\nMale"
        self.assertEqual(AadhaarExtractor().extract_name(text), "Varun Kumar Gera")

    def test_address_drops_garbage_before_relation_marker(self):
        text = "Address\nVarese, D/O Mukesh Kumar\nH. No. E-376, Ashok Nagar, Delhi 110093\nUIDAI"
        address = self.base.extract_address(text)
        self.assertNotIn("Varese", address)
        self.assertIn("D/O Mukesh Kumar", address)

    def test_address_stops_after_pin_code(self):
        text = "Address\nS/O Narender Gera, 2F/63, Faridabad\nHaryana - 121001\nES (aOR Rs"
        address = self.base.extract_address(text)
        self.assertIn("121001", address)
        self.assertNotIn("ES (aOR Rs", address)

    def test_invalid_image_input_is_safe(self):
        with self.assertRaises(ExtractionError):
            extract_from_bytes(b"not an image")

    def test_pan_and_driving_licence_masking(self):
        self.assertEqual(mask_pan("ABCDE1234F"), "XXXXX1234F")
        self.assertEqual(mask_driving_licence("DL-1420110012345"), "XXXXXXXXXXX2345")


if __name__ == "__main__":
    unittest.main()
