"""Export compact, browser-ready assets for the flAtlas web app."""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOLD_DIR = PROJECT_ROOT / "2_local_processing" / "3_gold"
PUBLIC_OUTPUT_DIR = PROJECT_ROOT / "web" / "public" / "data"
PRIVATE_OUTPUT_DIR = PROJECT_ROOT / "backend" / "data"
FREE_TRANSACTION_YEARS = 5
DISTRICT_SOURCE = GOLD_DIR / "district_geometry_london_flats.gpkg"
LSOA_SOURCE = GOLD_DIR / "socio_economic_postcode_london_flats.gpkg"
TRANSACTION_SOURCE = GOLD_DIR / "district_transactions_london_flats.csv"
TRANSACTION_METADATA_SOURCE = GOLD_DIR / "london_transaction_source.json"
BOUNDARY_METADATA_SOURCE = GOLD_DIR / "postcode_district_boundary_source.json"

DISTRICT_FIELDS = {
    "PostDist": "district",
    "AreaName": "areaName",
    "HasSocioeconomicSummary": "hasSocioeconomicSummary",
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
    PUBLIC_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PRIVATE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    district_source = gpd.read_file(DISTRICT_SOURCE)
    lsoa_source = gpd.read_file(LSOA_SOURCE)
    transactions = pd.read_csv(TRANSACTION_SOURCE)
    transaction_metadata = json.loads(
        TRANSACTION_METADATA_SOURCE.read_text(encoding="utf-8")
    )
    boundary_metadata = json.loads(
        BOUNDARY_METADATA_SOURCE.read_text(encoding="utf-8")
    )

    required_transaction_fields = {
        "postcode_district",
        "year",
        "num_transactions",
        "avg_price",
        "median_price",
    }
    missing_fields = required_transaction_fields - set(transactions.columns)
    if missing_fields:
        raise ValueError(f"Transaction source is missing fields: {sorted(missing_fields)}")

    districts = district_source[list(DISTRICT_FIELDS) + ["geometry"]].rename(
        columns=DISTRICT_FIELDS
    )
    district_codes = set(districts["district"])

    transactions = transactions.loc[
        transactions["postcode_district"].isin(district_codes)
    ].copy()
    transactions = transactions.sort_values(["postcode_district", "year"])
    if transactions.duplicated(["postcode_district", "year"]).any():
        raise ValueError("Transaction source contains duplicate district-year rows")
    if transactions["postcode_district"].nunique() != len(district_codes):
        raise ValueError("Transaction source does not cover every mapped postcode district")
    source_latest_year = int(transaction_metadata["years"][1])
    if int(transactions["year"].max()) != source_latest_year:
        raise ValueError(
            "Transaction rows and source metadata disagree on the latest year"
        )

    histories: dict[str, list[dict[str, int | float]]] = {}
    for district, group in transactions.groupby("postcode_district", sort=True):
        histories[district] = [
            {
                "year": int(row.year),
                "transactions": int(row.num_transactions),
                "averagePrice": _clean_number(row.avg_price, 0),
                "medianPrice": _clean_number(row.median_price, 0),
            }
            for _, row in group.iterrows()
        ]

    district_records = []
    for _, row in districts.drop(columns="geometry").sort_values("district").iterrows():
        record = {}
        for key in DISTRICT_FIELDS.values():
            if key in {"district", "areaName"}:
                record[key] = row[key]
            elif key == "hasSocioeconomicSummary":
                if pd.isna(row[key]):
                    raise ValueError(
                        f"District {row['district']} has no socioeconomic availability flag"
                    )
                record[key] = bool(row[key])
            else:
                record[key] = _clean_number(row[key], 4)
        record["history"] = histories.get(row["district"], [])
        district_records.append(record)

    district_geometry = districts[["district", "areaName", "geometry"]].to_crs(27700)
    district_geometry["geometry"] = district_geometry.geometry.simplify(
        tolerance=12, preserve_topology=True
    )
    district_geometry = district_geometry.to_crs(4326)
    if district_geometry.geometry.is_empty.any() or not district_geometry.geometry.is_valid.all():
        raise ValueError("District browser geometry contains empty or invalid features")

    lsoas = lsoa_source[list(LSOA_FIELDS) + ["geometry"]].rename(columns=LSOA_FIELDS)
    lsoas = lsoas.to_crs(27700)
    lsoas["geometry"] = lsoas.geometry.simplify(tolerance=18, preserve_topology=True)
    lsoas = lsoas.to_crs(4326)
    if lsoas.geometry.is_empty.any() or not lsoas.geometry.is_valid.all():
        raise ValueError("LSOA browser geometry contains empty or invalid features")
    for field in set(LSOA_FIELDS.values()) - {
        "lsoaCode",
        "lsoaName",
        "district",
        "assignmentConfidence",
        "includedInDistrictSummary",
    }:
        decimals = 4 if field == "overlapShare" else 2
        lsoas[field] = lsoas[field].map(
            lambda value: _clean_number(value, decimals)
        )

    years = sorted(int(year) for year in transactions["year"].unique())
    latest_year = max(years)
    latest_complete_year = int(transaction_metadata["latestCompleteYear"])
    metadata = {
        "generatedFrom": {
            "transactions": TRANSACTION_SOURCE.name,
            "districts": DISTRICT_SOURCE.name,
            "lsoas": LSOA_SOURCE.name,
        },
        "dataAsOf": transaction_metadata["latestTransferDate"],
        "boundarySource": boundary_metadata["source"],
        "boundarySources": boundary_metadata["sources"],
        "boundaryMethod": boundary_metadata["method"],
        "boundarySourceRetrievedOn": boundary_metadata["retrievedOn"],
        "centralBoundaryCoverageShare": boundary_metadata["currentValidation"][
            "coverageShare"
        ],
        "centralBoundaryDistrictMatchShare": boundary_metadata[
            "currentValidation"
        ]["matchingDistrictShare"],
        "districtCount": len(districts),
        "lsoaCount": len(lsoas),
        "years": years,
        "latestCompleteYear": latest_complete_year,
        "latestYear": latest_year,
        "latestYearIsPartial": latest_year > latest_complete_year,
        "transactionCount": int(transactions["num_transactions"].sum()),
    }

    free_years = set(
        year for year in years if year <= latest_complete_year
    )
    free_years = set(sorted(free_years)[-FREE_TRANSACTION_YEARS:])
    free_records = []
    for record in district_records:
        free_record = {
            **record,
            "population": None,
            "populationDensity": None,
            "income": None,
            "employment": None,
            "education": None,
            "health": None,
            "crime": None,
            "housingBarriers": None,
            "environment": None,
            "history": [
                item for item in record["history"] if item["year"] in free_years
            ],
        }
        free_records.append(free_record)

    _write_json(PUBLIC_OUTPUT_DIR / "metadata.json", metadata)
    _write_json(PUBLIC_OUTPUT_DIR / "districts.json", free_records)
    _write_json(
        PUBLIC_OUTPUT_DIR / "district-boundaries.geojson",
        _geojson_payload(district_geometry, "district"),
    )
    public_lsoa_path = PUBLIC_OUTPUT_DIR / "lsoa-boundaries.geojson"
    if public_lsoa_path.exists():
        public_lsoa_path.unlink()

    _write_json(PRIVATE_OUTPUT_DIR / "metadata.json", metadata)
    _write_json(PRIVATE_OUTPUT_DIR / "districts.private.json", district_records)
    _write_json(
        PRIVATE_OUTPUT_DIR / "lsoa.private.geojson",
        _geojson_payload(lsoas, "lsoaCode"),
    )

    public_sizes = {
        path.name: round(path.stat().st_size / 1_000_000, 2)
        for path in sorted(PUBLIC_OUTPUT_DIR.iterdir())
    }
    private_sizes = {
        path.name: round(path.stat().st_size / 1_000_000, 2)
        for path in sorted(PRIVATE_OUTPUT_DIR.iterdir())
    }
    print(
        f"Exported {len(districts)} districts and {len(lsoas)} LSOAs: "
        f"public={public_sizes}, private={private_sizes}"
    )


if __name__ == "__main__":
    export()
