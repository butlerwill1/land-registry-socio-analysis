"""Tests for 2021 LSOA to postcode-district mapping."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import box


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "2_local_processing"))

from lsoa_mapping import (  # noqa: E402
    aggregate_lsoas_to_districts,
    assign_lsoas_by_largest_overlap,
)


class LargestOverlapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.districts = gpd.GeoDataFrame(
            {
                "PostDist": ["A1", "B1"],
                "geometry": [box(0, 0, 10, 10), box(10, 0, 20, 10)],
            },
            crs="EPSG:27700",
        )
        self.lsoas = gpd.GeoDataFrame(
            {
                "LSOA21CD": ["FULL", "CROSS", "SLIVER", "TINY"],
                "LSOA21NM": ["Full", "Cross", "Sliver", "Tiny"],
                "geometry": [
                    box(1, 1, 4, 4),
                    box(8, 1, 14, 4),
                    box(9.9, 5, 13, 8),
                    box(19.9, 1, 30, 4),
                ],
            },
            crs="EPSG:27700",
        )

    def test_assigns_largest_area_not_first_intersection(self) -> None:
        result = assign_lsoas_by_largest_overlap(self.lsoas, self.districts)
        assignments = result.set_index("LSOA21CD")

        self.assertEqual(assignments.loc["FULL", "PostDist"], "A1")
        self.assertEqual(assignments.loc["FULL", "assignment_method"], "fully_within")
        self.assertEqual(assignments.loc["CROSS", "PostDist"], "B1")
        self.assertAlmostEqual(assignments.loc["CROSS", "overlap_share"], 2 / 3, places=3)
        self.assertEqual(assignments.loc["SLIVER", "PostDist"], "B1")
        self.assertGreater(assignments.loc["SLIVER", "overlap_share"], 0.96)
        self.assertFalse(assignments.loc["TINY", "included_in_district_summary"])

    def test_aggregation_is_population_weighted(self) -> None:
        assigned = assign_lsoas_by_largest_overlap(self.lsoas.iloc[:2], self.districts)
        assigned["PostDist"] = "A1"
        assigned["LADName"] = "Authority"
        assigned["TotalPopulation"] = assigned["LSOA21CD"].map(
            {"FULL": 100, "CROSS": 300}
        )
        assigned["DependentChildren"] = assigned["TotalPopulation"] * 0.2
        assigned["Population60Plus"] = assigned["TotalPopulation"] * 0.1
        assigned["WorkingAgePopulation"] = assigned["TotalPopulation"] * 0.7
        assigned["OverallScore"] = assigned["LSOA21CD"].map(
            {"FULL": 10.0, "CROSS": 30.0}
        )
        assigned["OverallRank"] = assigned["LSOA21CD"].map(
            {"FULL": 100.0, "CROSS": 300.0}
        )

        result = aggregate_lsoas_to_districts(assigned, self.districts)
        values = result.set_index("PostDist")

        self.assertEqual(values.loc["A1", "OverallAvg"], 25.0)
        self.assertEqual(values["TotalPopulation"].sum(), 400)


if __name__ == "__main__":
    unittest.main()
