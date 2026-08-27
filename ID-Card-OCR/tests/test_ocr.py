"""Tests that do not require an installed external Tesseract executable."""

from __future__ import annotations

import unittest

import numpy as np

from src.preprocessing import image_to_bgr, preprocess_image, remove_qr_code
from src.text_cleaner import clean_address, clean_text


class PreprocessingTests(unittest.TestCase):
    def test_invalid_array_is_rejected(self):
        with self.assertRaises(ValueError):
            image_to_bgr(np.array([]))

    def test_preprocessing_keeps_image_dimensions_reasonable(self):
        image = np.full((120, 200, 3), 180, dtype=np.uint8)
        output = preprocess_image(image)
        self.assertEqual(output.ndim, 2)
        self.assertGreaterEqual(output.shape[1], 200)

    def test_qr_removal_returns_an_image_when_no_qr_exists(self):
        image = np.full((80, 120, 3), 255, dtype=np.uint8)
        output, regions = remove_qr_code(image, return_coordinates=True)
        self.assertEqual(output.shape, image.shape)
        self.assertEqual(regions, [])

    def test_text_cleaning_preserves_address_punctuation(self):
        self.assertEqual(clean_text("A  \tB\n\n\nC"), "A B\n\nC")
        self.assertEqual(clean_address("H.No. 2/4, Main-Road #7"), "H.No. 2/4, Main-Road #7")


if __name__ == "__main__":
    unittest.main()
