"""End-to-end quality checks for the exported London atlas data."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point, shape


PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_DATA_DIR = PROJECT_ROOT / "web" / "public" / "data"
sys.path.insert(0, str(PROJECT_ROOT / "2_local_processing"))

from postcode_boundaries import validate_topology  # noqa: E402

LANDMARKS = {
    "Westminster": Point(-0.1276, 51.5033),
    "Soho": Point(-0.1340, 51.5130),
    "Mayfair": Point(-0.1470, 51.5100),
    "Holborn": Point(-0.1170, 51.5175),
    "City of London": Point(-0.0900, 51.5150),
}
EXPECTED_CENTRAL_DISTRICTS = {
    "EC1A",
    "EC2A",
    "EC3A",
    "EC4A",
    "SW1A",
    "W1F",
    "W1J",
    "WC1A",
    "WC2A",
}


def _load_json(name: str) -> object:
    return json.loads((WEB_DATA_DIR / name).read_text(encoding="utf-8"))


class LondonAtlasDataQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.metadata = _load_json("metadata.json")
        cls.districts = _load_json("districts.json")
        cls.boundaries = _load_json("district-boundaries.geojson")
        cls.lsoas = _load_json("lsoa-boundaries.geojson")

        cls.records_by_district = {
            record["district"]: record for record in cls.districts
        }
        cls.geometries_by_district = {
            feature["properties"]["district"]: shape(feature["geometry"])
            for feature in cls.boundaries["features"]
        }

    def test_central_districts_and_landmarks_are_covered(self) -> None:
        self.assertGreaterEqual(
            self.metadata["centralBoundaryCoverageShare"],
            0.98,
        )
        self.assertGreaterEqual(
            self.metadata["centralBoundaryDistrictMatchShare"],
            0.90,
        )
        self.assertTrue(
            EXPECTED_CENTRAL_DISTRICTS.issubset(self.geometries_by_district)
        )
        for name, point in LANDMARKS.items():
            matches = [
                district
                for district, geometry in self.geometries_by_district.items()
                if geometry.covers(point)
            ]
            with self.subTest(landmark=name):
                self.assertEqual(len(matches), 1, matches)

    def test_every_exported_district_has_geometry_and_transaction_history(self) -> None:
        self.assertEqual(
            set(self.records_by_district),
            set(self.geometries_by_district),
        )
        for district, record in self.records_by_district.items():
            with self.subTest(district=district):
                self.assertTrue(record["history"])
                self.assertTrue(self.geometries_by_district[district].is_valid)

        districts_with_2025_sales = {
            district
            for district, record in self.records_by_district.items()
            if any(item["year"] == 2025 for item in record["history"])
        }
        self.assertEqual(len(districts_with_2025_sales), 308)
        self.assertTrue(EXPECTED_CENTRAL_DISTRICTS.issubset(districts_with_2025_sales))

    def test_partial_year_and_transaction_totals_are_explicit(self) -> None:
        self.assertEqual(self.metadata["latestCompleteYear"], 2025)
        self.assertEqual(self.metadata["latestYear"], 2026)
        self.assertTrue(self.metadata["latestYearIsPartial"])
        self.assertEqual(self.metadata["dataAsOf"], "2026-01-30")

        history_total = sum(
            item["transactions"]
            for record in self.records_by_district.values()
            for item in record["history"]
        )
        self.assertEqual(history_total, self.metadata["transactionCount"])

    def test_boundary_provenance_includes_both_polygon_sources(self) -> None:
        source_names = {
            source["name"] for source in self.metadata["boundarySources"]
        }
        self.assertIn(
            "Greater London Authority Postcode Units ArcGIS layer",
            source_names,
        )
        self.assertIn("GeoLytix postal boundaries 2012", source_names)

    def test_lsoas_reference_exported_districts(self) -> None:
        exported_districts = set(self.records_by_district)
        lsoa_districts = {
            feature["properties"]["district"]
            for feature in self.lsoas["features"]
        }
        self.assertTrue(lsoa_districts.issubset(exported_districts))
        included_overlaps = [
            feature["properties"]["overlapShare"]
            for feature in self.lsoas["features"]
            if feature["properties"]["includedInDistrictSummary"]
        ]
        self.assertTrue(included_overlaps)
        self.assertGreaterEqual(min(included_overlaps), 0.999)

    def test_source_district_boundaries_do_not_overlap(self) -> None:
        source = gpd.read_file(
            PROJECT_ROOT
            / "2_local_processing"
            / "3_gold"
            / "postcode_district_boundaries_london.gpkg",
            layer="districts",
        )
        result = validate_topology(source)
        self.assertEqual(result["positiveAreaOverlapPairs"], 0)

    def test_missing_socioeconomic_summaries_are_not_fabricated(self) -> None:
        w1f = self.records_by_district["W1F"]
        self.assertFalse(w1f["hasSocioeconomicSummary"])
        self.assertIsNone(w1f["overall"])
        self.assertGreater(
            next(item["transactions"] for item in w1f["history"] if item["year"] == 2025),
            0,
        )


if __name__ == "__main__":
    unittest.main()
