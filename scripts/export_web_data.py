"""Export compact, browser-ready assets for the London Flat Atlas web app."""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOLD_DIR = PROJECT_ROOT / "2_local_processing" / "3_gold"
OUTPUT_DIR = PROJECT_ROOT / "web" / "public" / "data"
DISTRICT_SOURCE = GOLD_DIR / "district_geometry_london_flats.gpkg"
LSOA_SOURCE = GOLD_DIR / "socio_economic_postcode_london_flats.gpkg"
TRANSACTION_SOURCE = PROJECT_ROOT / "district_groupby_price_graph.csv"

DISTRICT_FIELDS = {
    "PostDist": "district",
    "AreaName": "areaName",
    "CountLowLevelAreas": "lsoaCount",
    "ExcludedAmbiguousLSOAs": "excludedLsoaCount",
    "MeanOverlapShare": "meanOverlapShare",
    "AreaKm2": "areaKm2",
    "TotalPopulation": "population",
    "PopulationDensity": "populationDensity",
    "OverallAvg": "overall",
    "IncomeAvg": "income",
    "EmploymentAvg": "employment",
    "EducationAvg": "education",
    "HealthAvg": "health",
    "CrimeAvg": "crime",
    "HousingBarriersAvg": "housingBarriers",
    "EnvironmentAvg": "environment",
}

LSOA_FIELDS = {
    "LSOA21CD": "lsoaCode",
    "LSOA21NM": "lsoaName",
    "PostDist": "district",
    "overlap_share": "overlapShare",
    "assignment_confidence": "assignmentConfidence",
    "included_in_district_summary": "includedInDistrictSummary",
    "OverallScore": "overall",
    "IncomeScore": "income",
    "EmploymentScore": "employment",
    "EducationScore": "education",
    "HealthScore": "health",
    "CrimeScore": "crime",
    "HousingBarriersScore": "housingBarriers",
    "EnvironmentScore": "environment",
    "TotalPopulation": "population",
}


def _clean_number(value: object, decimals: int = 2) -> int | float | None:
    if value is None or pd.isna(value):
        return None
    number = float(value)
    if number.is_integer():
        return int(number)
    return round(number, decimals)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=True, separators=(",", ":")),
        encoding="utf-8",
    )


def _geojson_payload(frame: gpd.GeoDataFrame, id_column: str) -> dict:
    payload = json.loads(frame.to_json(drop_id=True))
    for feature in payload["features"]:
        feature["id"] = feature["properties"][id_column]
    return payload


def export() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    district_source = gpd.read_file(DISTRICT_SOURCE)
    lsoa_source = gpd.read_file(LSOA_SOURCE)
    transactions = pd.read_csv(TRANSACTION_SOURCE)

    districts = district_source[list(DISTRICT_FIELDS) + ["geometry"]].rename(
        columns=DISTRICT_FIELDS
    )
    district_codes = set(districts["district"])

    transactions = transactions.loc[
        transactions["postcode_district"].isin(district_codes)
        & transactions["property_type"].eq("Flat")
    ].copy()
    transactions = transactions.sort_values(["postcode_district", "year"])

    histories: dict[str, list[dict[str, int | float]]] = {}
    for district, group in transactions.groupby("postcode_district", sort=True):
        histories[district] = [
            {
                "year": int(row.year),
                "transactions": int(row.num_transactions),
                "averagePrice": _clean_number(row.avg_price, 0),
                "medianPrice": _clean_number(row["50th_percentile_price"], 0),
            }
            for _, row in group.iterrows()
        ]

    district_records = []
    for _, row in districts.drop(columns="geometry").sort_values("district").iterrows():
        record = {
            key: (_clean_number(row[key], 4) if key not in {"district", "areaName"} else row[key])
            for key in DISTRICT_FIELDS.values()
        }
        record["history"] = histories.get(row["district"], [])
        district_records.append(record)

    district_geometry = districts[["district", "areaName", "geometry"]].to_crs(27700)
    district_geometry["geometry"] = district_geometry.geometry.simplify(
        tolerance=12, preserve_topology=True
    )
    district_geometry = district_geometry.to_crs(4326)

    lsoas = lsoa_source[list(LSOA_FIELDS) + ["geometry"]].rename(columns=LSOA_FIELDS)
    lsoas = lsoas.to_crs(27700)
    lsoas["geometry"] = lsoas.geometry.simplify(tolerance=18, preserve_topology=True)
    lsoas = lsoas.to_crs(4326)
    for field in set(LSOA_FIELDS.values()) - {
        "lsoaCode",
        "lsoaName",
        "district",
        "assignmentConfidence",
        "includedInDistrictSummary",
    }:
        lsoas[field] = lsoas[field].map(_clean_number)

    years = sorted(int(year) for year in transactions["year"].unique())
    metadata = {
        "generatedFrom": {
            "transactions": TRANSACTION_SOURCE.name,
            "districts": DISTRICT_SOURCE.name,
            "lsoas": LSOA_SOURCE.name,
        },
        "districtCount": len(districts),
        "lsoaCount": len(lsoas),
        "years": years,
        "latestCompleteYear": 2025,
        "latestYear": max(years),
        "transactionCount": int(transactions["num_transactions"].sum()),
    }

    _write_json(OUTPUT_DIR / "metadata.json", metadata)
    _write_json(OUTPUT_DIR / "districts.json", district_records)
    _write_json(
        OUTPUT_DIR / "district-boundaries.geojson",
        _geojson_payload(district_geometry, "district"),
    )
    _write_json(
        OUTPUT_DIR / "lsoa-boundaries.geojson",
        _geojson_payload(lsoas, "lsoaCode"),
    )

    sizes = {
        path.name: round(path.stat().st_size / 1_000_000, 2)
        for path in sorted(OUTPUT_DIR.iterdir())
    }
    print(f"Exported {len(districts)} districts and {len(lsoas)} LSOAs: {sizes}")


if __name__ == "__main__":
    export()
