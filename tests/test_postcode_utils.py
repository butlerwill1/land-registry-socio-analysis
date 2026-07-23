"""Tests for postcode parsing and London classification."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "1_spark_processing" / "3_gold"))

from postcode_utils import classify_london_postcode, split_postcode  # noqa: E402


class PostcodeParsingTests(unittest.TestCase):
    def test_extracts_leading_area_letters_only(self) -> None:
        self.assertEqual(split_postcode("SW1A 1AA"), ("SW", "SW1A", "SW1A-1"))
        self.assertEqual(split_postcode("W1H 7BH"), ("W", "W1H", "W1H-7"))
        self.assertEqual(split_postcode("EC1V 9NR"), ("EC", "EC1V", "EC1V-9"))

    def test_normalises_case_and_rejects_malformed_values(self) -> None:
        self.assertEqual(split_postcode("  wc2h 7lt "), ("WC", "WC2H", "WC2H-7"))
        self.assertEqual(
            split_postcode("not-a-postcode"),
            ("Unknown", "Unknown", "Unknown"),
        )
        self.assertEqual(split_postcode(None), ("Unknown", "Unknown", "Unknown"))

    def test_classifies_letter_suffixed_central_districts(self) -> None:
        central_examples = [
            ("EC", "EC2V"),
            ("WC", "WC1A"),
            ("W", "W1H"),
            ("SW", "SW1A"),
            ("E", "E1W"),
        ]
        for area, district in central_examples:
            with self.subTest(district=district):
                self.assertEqual(
                    classify_london_postcode(area, district),
                    "Central London",
                )

        self.assertEqual(classify_london_postcode("W", "W10"), "Greater London")
        self.assertEqual(classify_london_postcode("M", "M1"), "Outside London")


if __name__ == "__main__":
    unittest.main()
