"""Rebuild London-flats socioeconomic assets using official 2021 LSOAs."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import geopandas as gpd
import pandas as pd

from lsoa_mapping import (
    aggregate_lsoas_to_districts,
    assign_lsoas_by_largest_overlap,
    download_imd_2025_csv,
    ensure_wgs84,
    fetch_lsoa2021_for_bounds,
    load_imd_2025,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOLD_DIR = PROJECT_ROOT / "2_local_processing" / "3_gold"
SOURCE_DIR = PROJECT_ROOT / "2_local_processing" / "1_bronze" / "official_imd2025"


def _write_geopackage_atomically(data: gpd.GeoDataFrame, destination: Path) -> None:
    temporary = destination.with_name(f"{destination.stem}.tmp.gpkg")
    if temporary.exists():
        temporary.unlink()
    data.to_file(temporary, layer="socio", driver="GPKG", index=False)
    os.replace(temporary, destination)


def rebuild(refresh_sources: bool = False) -> None:
    district_source_path = GOLD_DIR / "postcode_district_boundaries_london.gpkg"
    district_output_path = GOLD_DIR / "district_geometry_london_flats.gpkg"
    transaction_path = GOLD_DIR / "district_transactions_london_flats.csv"
    lsoa_output_path = GOLD_DIR / "socio_economic_postcode_london_flats.gpkg"
    geometry_cache = SOURCE_DIR / "lsoa_2021_london_postcode_extent.geojson"
    imd_csv = SOURCE_DIR / "imd_2025_file_7.csv"

    print("Loading corrected postcode-district boundaries...")
    districts = gpd.read_file(
        district_source_path,
        layer="districts",
    )[["PostDist", "geometry"]]
    districts = ensure_wgs84(districts)
    transaction_districts = set(
        pd.read_csv(transaction_path, usecols=["postcode_district"])[
            "postcode_district"
        ].unique()
    )
    districts = districts[districts["PostDist"].isin(transaction_districts)].copy()
    missing_boundaries = sorted(transaction_districts - set(districts["PostDist"]))
    if missing_boundaries:
        raise ValueError(
            f"Transaction districts without postcode boundaries: {missing_boundaries}"
        )
    print(f"Loaded {len(districts):,} postcode districts with flat transactions")

    print("Fetching official 2021 LSOA polygons for the district extent...")
    lsoas = fetch_lsoa2021_for_bounds(
        tuple(districts.total_bounds),
        cache_path=geometry_cache,
        refresh=refresh_sources,
    )
    print(f"Loaded {len(lsoas):,} candidate 2021 LSOAs")

    print("Downloading and loading corrected IMD 2025 data...")
    download_imd_2025_csv(imd_csv, refresh=refresh_sources)
    imd = load_imd_2025(imd_csv)

    print("Assigning each LSOA to its largest-overlap postcode district...")
    assigned = assign_lsoas_by_largest_overlap(lsoas, districts)
    assigned = assigned.merge(
        imd,
        how="inner",
        left_on="LSOA21CD",
        right_on="LSOACode",
        validate="one_to_one",
    )
    assigned = gpd.GeoDataFrame(assigned, geometry="geometry", crs="EPSG:4326")
    if len(assigned) == 0:
        raise ValueError("No assigned LSOAs matched the official IMD 2025 table")
    print(f"Mapped {len(assigned):,} LSOAs with IMD data")

    print("Creating population-weighted postcode-district summaries...")
    summarised_districts = aggregate_lsoas_to_districts(assigned, districts)
    summary_attributes = summarised_districts.drop(columns="geometry")
    district_socio = districts.merge(
        summary_attributes,
        on="PostDist",
        how="left",
        validate="one_to_one",
    )
    district_socio = gpd.GeoDataFrame(
        district_socio,
        geometry="geometry",
        crs="EPSG:4326",
    )
    required_summary_fields = [
        "AreaName",
        "CountLowLevelAreas",
        "TotalPopulation",
        "OverallAvg",
        "IncomeAvg",
        "EmploymentAvg",
        "EducationAvg",
        "HealthAvg",
        "CrimeAvg",
        "HousingBarriersAvg",
        "EnvironmentAvg",
    ]
    has_socio = (
        district_socio["CountLowLevelAreas"].fillna(0).gt(0)
        & district_socio[required_summary_fields].notna().all(axis=1)
    )
    missing_socio = ~has_socio
    district_socio.loc[missing_socio, "AreaName"] = "Central London"
    district_socio.loc[missing_socio, "CountLowLevelAreas"] = 0
    district_socio.loc[missing_socio, "CandidateLowLevelAreas"] = 0
    district_socio.loc[missing_socio, "ExcludedAmbiguousLSOAs"] = 0
    district_socio.loc[missing_socio, "FullyWithinLSOAs"] = 0
    district_socio.loc[missing_socio, "BoundaryCrossingLSOAs"] = 0
    district_socio.loc[missing_socio, "LowConfidenceLSOAs"] = 0
    district_socio["HasSocioeconomicSummary"] = has_socio
    district_socio["AreaKm2"] = (
        district_socio.to_crs(27700).geometry.area / 1_000_000
    ).round(3)

    print("Writing dashboard GeoPackages...")
    _write_geopackage_atomically(assigned, lsoa_output_path)
    _write_geopackage_atomically(district_socio, district_output_path)

    confidence_counts = assigned["assignment_confidence"].value_counts().to_dict()
    excluded_count = int((~assigned["included_in_district_summary"]).sum())
    print("LSOA 2021 rebuild complete")
    print(f"  Districts: {len(district_socio):,}")
    print(f"  Districts without a majority-overlap LSOA: {int(missing_socio.sum()):,}")
    print(f"  LSOAs: {len(assigned):,}")
    print(f"  Assignment confidence: {confidence_counts}")
    print(f"  Excluded from district summaries (<50% overlap): {excluded_count:,}")
    print(f"  District output: {district_output_path}")
    print(f"  LSOA output: {lsoa_output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh-sources",
        action="store_true",
        help="Download fresh copies of the official LSOA geometry and IMD table.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    rebuild(refresh_sources=arguments.refresh_sources)
