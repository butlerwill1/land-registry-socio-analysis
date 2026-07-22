"""Rebuild London-flats socioeconomic assets using official 2021 LSOAs."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import geopandas as gpd

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
    district_path = GOLD_DIR / "district_geometry_london_flats.gpkg"
    lsoa_output_path = GOLD_DIR / "socio_economic_postcode_london_flats.gpkg"
    geometry_cache = SOURCE_DIR / "lsoa_2021_london_postcode_extent.geojson"
    imd_csv = SOURCE_DIR / "imd_2025_file_7.csv"

    print("Loading existing postcode-district boundaries...")
    districts = gpd.read_file(district_path, layer="socio")[["PostDist", "geometry"]]
    districts = ensure_wgs84(districts)
    print(f"Loaded {len(districts):,} postcode districts")

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
    district_socio = aggregate_lsoas_to_districts(assigned, districts)
    missing_districts = sorted(set(districts["PostDist"]) - set(district_socio["PostDist"]))
    if missing_districts:
        raise ValueError(f"Districts without assigned LSOAs: {missing_districts}")

    print("Writing dashboard GeoPackages...")
    _write_geopackage_atomically(assigned, lsoa_output_path)
    _write_geopackage_atomically(district_socio, district_path)

    confidence_counts = assigned["assignment_confidence"].value_counts().to_dict()
    excluded_count = int((~assigned["included_in_district_summary"]).sum())
    print("LSOA 2021 rebuild complete")
    print(f"  Districts: {len(district_socio):,}")
    print(f"  LSOAs: {len(assigned):,}")
    print(f"  Assignment confidence: {confidence_counts}")
    print(f"  Excluded from district summaries (<50% overlap): {excluded_count:,}")
    print(f"  District output: {district_path}")
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
