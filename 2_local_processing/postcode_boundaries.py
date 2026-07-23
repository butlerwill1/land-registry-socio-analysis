"""Build a complete Central London postcode-district boundary source."""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from lsoa_mapping import ensure_wgs84


PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOLD_DIR = PROJECT_ROOT / "2_local_processing" / "3_gold"
SOURCE_DIR = PROJECT_ROOT / "2_local_processing" / "1_bronze" / "gla_postcodes"

BASELINE_DISTRICTS = GOLD_DIR / "district_geometry_london_flats.gpkg"
CENTRAL_UNIT_CACHE = SOURCE_DIR / "central_postcode_units.gpkg"
CURRENT_POSTCODE_CACHE = SOURCE_DIR / "ons_live_central_postcodes.gpkg"
OUTPUT_PATH = GOLD_DIR / "postcode_district_boundaries_london.gpkg"
SOURCE_METADATA_PATH = GOLD_DIR / "postcode_district_boundary_source.json"

GLA_POSTCODE_UNIT_URL = (
    "https://gis.london.gov.uk/arcgis/rest/services/IMA_explorer/"
    "ima_context_public_02/MapServer/8/query"
)
ONS_LIVE_POSTCODE_URL = (
    "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
    "Online_ONS_Postcode_Directory_Live/FeatureServer/1/query"
)
ONS_POSTCODE_REFERENCE_DATE = "February 2026"
ARCGIS_BATCH_SIZE = 1_000
CENTRAL_DISTRICT_PATTERN = re.compile(
    r"^(?:EC\d[A-Z]?|WC\d[A-Z]?|W1[A-Z]|SW1[A-Z])$"
)
NON_GEOGRAPHIC_CENTRAL_DISTRICTS = frozenset({"EC1P", "EC3P", "EC4P"})

LANDMARKS = {
    "Westminster": (-0.1276, 51.5033),
    "Soho": (-0.1340, 51.5130),
    "Mayfair": (-0.1470, 51.5100),
    "Holborn": (-0.1170, 51.5175),
    "City of London": (-0.0900, 51.5150),
}


def _request_json(
    params: dict[str, str],
    method: str = "GET",
    url: str = GLA_POSTCODE_UNIT_URL,
) -> dict:
    encoded = urllib.parse.urlencode(params)
    request_url = f"{url}?{encoded}" if method == "GET" else url
    body = None if method == "GET" else encoded.encode("ascii")
    request = urllib.request.Request(
        request_url,
        data=body,
        headers={
            "User-Agent": "land-registry-socio-analysis/1.0",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method=method,
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def _central_district_codes() -> list[str]:
    payload = _request_json(
        {
            "where": "1=1",
            "outFields": "pc_district",
            "returnGeometry": "false",
            "returnDistinctValues": "true",
            "orderByFields": "pc_district",
            "f": "json",
        }
    )
    codes = [
        feature["attributes"]["pc_district"]
        for feature in payload.get("features", [])
    ]
    selected = sorted(code for code in codes if CENTRAL_DISTRICT_PATTERN.fullmatch(code))
    if not selected:
        raise ValueError("The GLA postcode service returned no Central London districts")
    return selected


def fetch_central_postcode_units(refresh: bool = False) -> gpd.GeoDataFrame:
    """Fetch GLA postcode-unit polygons for EC, WC, W1, and SW1 districts."""
    if CENTRAL_UNIT_CACHE.exists() and not refresh:
        return ensure_wgs84(gpd.read_file(CENTRAL_UNIT_CACHE))

    district_codes = _central_district_codes()
    sql_values = ",".join(f"'{code}'" for code in district_codes)
    where = f"pc_district IN ({sql_values})"
    id_payload = _request_json(
        {
            "where": where,
            "returnIdsOnly": "true",
            "returnGeometry": "false",
            "f": "json",
        }
    )
    object_ids = sorted(id_payload.get("objectIds", []))
    if not object_ids:
        raise ValueError("The GLA postcode service returned no Central London units")

    features: list[dict] = []
    for start in range(0, len(object_ids), ARCGIS_BATCH_SIZE):
        batch = object_ids[start : start + ARCGIS_BATCH_SIZE]
        payload = _request_json(
            {
                "objectIds": ",".join(str(object_id) for object_id in batch),
                "outFields": "pc_district",
                "returnGeometry": "true",
                "outSR": "4326",
                "f": "geojson",
            },
            method="POST",
        )
        page = payload.get("features", [])
        if len(page) != len(batch):
            raise ValueError(
                f"Expected {len(batch)} postcode units, received {len(page)}"
            )
        features.extend(page)

    units = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    units = units[["pc_district", "geometry"]].rename(
        columns={"pc_district": "PostDist"}
    )
    units["geometry"] = units.geometry.make_valid()
    if units.geometry.is_empty.any() or not units.geometry.is_valid.all():
        raise ValueError("The GLA postcode service returned invalid unit geometry")

    CENTRAL_UNIT_CACHE.parent.mkdir(parents=True, exist_ok=True)
    units.to_file(CENTRAL_UNIT_CACHE, layer="postcode_units", driver="GPKG", index=False)
    return units


def dissolve_central_districts(units: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Dissolve current postcode-unit polygons into postcode districts."""
    units = ensure_wgs84(units)[["PostDist", "geometry"]]
    districts = units.dissolve(by="PostDist", as_index=False)
    districts["geometry"] = districts.geometry.make_valid()
    districts = districts.sort_values("PostDist").reset_index(drop=True)
    if districts.geometry.is_empty.any() or not districts.geometry.is_valid.all():
        raise ValueError("Dissolving postcode units produced invalid district geometry")
    return districts


def fetch_current_central_postcodes(refresh: bool = False) -> gpd.GeoDataFrame:
    """Fetch official live postcode centroids for currentness validation."""
    if CURRENT_POSTCODE_CACHE.exists() and not refresh:
        return ensure_wgs84(gpd.read_file(CURRENT_POSTCODE_CACHE))

    where = (
        "PCDS LIKE 'EC%' OR PCDS LIKE 'WC%' OR "
        "PCDS LIKE 'W1%' OR PCDS LIKE 'SW1%'"
    )
    id_payload = _request_json(
        {
            "where": where,
            "returnIdsOnly": "true",
            "returnGeometry": "false",
            "f": "json",
        },
        url=ONS_LIVE_POSTCODE_URL,
    )
    object_ids = sorted(id_payload.get("objectIds", []))
    if not object_ids:
        raise ValueError("The ONS live postcode service returned no central postcodes")

    features: list[dict] = []
    for start in range(0, len(object_ids), ARCGIS_BATCH_SIZE):
        batch = object_ids[start : start + ARCGIS_BATCH_SIZE]
        payload = _request_json(
            {
                "objectIds": ",".join(str(object_id) for object_id in batch),
                "outFields": "PCDS",
                "returnGeometry": "true",
                "outSR": "4326",
                "f": "geojson",
            },
            method="POST",
            url=ONS_LIVE_POSTCODE_URL,
        )
        page = payload.get("features", [])
        if len(page) != len(batch):
            raise ValueError(
                f"Expected {len(batch)} current postcodes, received {len(page)}"
            )
        features.extend(page)

    postcodes = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    postcodes = postcodes[["PCDS", "geometry"]]
    postcodes["PostDist"] = (
        postcodes["PCDS"].astype(str).str.strip().str.upper().str.split().str[0]
    )
    postcodes = postcodes[
        postcodes["PostDist"].str.fullmatch(CENTRAL_DISTRICT_PATTERN)
    ].copy()
    if postcodes.empty:
        raise ValueError("No current central postcodes matched the district pattern")

    CURRENT_POSTCODE_CACHE.parent.mkdir(parents=True, exist_ok=True)
    postcodes.to_file(
        CURRENT_POSTCODE_CACHE,
        layer="postcodes",
        driver="GPKG",
        index=False,
    )
    return postcodes


def validate_current_postcodes(
    central_districts: gpd.GeoDataFrame,
    current_postcodes: gpd.GeoDataFrame,
) -> dict[str, int | float | list[str]]:
    """Measure current ONS postcode coverage and reject grossly stale geometry."""
    central_districts = ensure_wgs84(central_districts)
    current_postcodes = ensure_wgs84(current_postcodes)
    geometry_by_district = central_districts.set_index("PostDist").geometry

    missing_districts = sorted(
        set(current_postcodes["PostDist"]) - set(geometry_by_district.index)
    )
    unexpected_missing = sorted(
        set(missing_districts) - NON_GEOGRAPHIC_CENTRAL_DISTRICTS
    )
    if unexpected_missing:
        raise ValueError(
            f"Current ONS postcodes have no district polygon: {unexpected_missing}"
        )
    postcodes_to_validate = current_postcodes[
        ~current_postcodes["PostDist"].isin(missing_districts)
    ].copy()

    joined = gpd.sjoin(
        postcodes_to_validate,
        central_districts[["PostDist", "geometry"]].rename(
            columns={"PostDist": "polygonDistrict"}
        ),
        how="left",
        predicate="within",
    )
    covered_count = int(joined["polygonDistrict"].notna().sum())
    matching_count = int(
        (joined["PostDist"] == joined["polygonDistrict"]).sum()
    )
    coverage_share = covered_count / len(postcodes_to_validate)
    matching_share = matching_count / len(postcodes_to_validate)
    if coverage_share < 0.98 or matching_share < 0.90:
        raise ValueError(
            "Central postcode polygons failed current ONS coverage thresholds: "
            f"coverage={coverage_share:.2%}, district match={matching_share:.2%}"
        )

    return {
        "postcodeCount": len(postcodes_to_validate),
        "districtCount": postcodes_to_validate["PostDist"].nunique(),
        "coveredByCentralGeometry": covered_count,
        "coverageShare": round(coverage_share, 4),
        "matchingDistrictCount": matching_count,
        "matchingDistrictShare": round(matching_share, 4),
        "nonGeographicDistrictsExcluded": missing_districts,
    }


def merge_with_baseline(central: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Replace incomplete central polygons while retaining outer-London coverage."""
    baseline = ensure_wgs84(
        gpd.read_file(BASELINE_DISTRICTS, layer="socio")[["PostDist", "geometry"]]
    )
    baseline = baseline[
        ~baseline["PostDist"].str.fullmatch(CENTRAL_DISTRICT_PATTERN)
    ].copy()
    central_metric = central.to_crs("EPSG:27700")
    baseline_metric = baseline.to_crs("EPSG:27700")
    central_footprint = central_metric.geometry.union_all()
    baseline_metric["geometry"] = baseline_metric.geometry.difference(
        central_footprint
    )
    baseline_metric = baseline_metric[~baseline_metric.geometry.is_empty].copy()
    combined = gpd.GeoDataFrame(
        pd.concat([baseline_metric, central_metric], ignore_index=True),
        geometry="geometry",
        crs="EPSG:27700",
    )
    combined["geometry"] = combined.geometry.make_valid()
    combined = combined.dissolve(by="PostDist", as_index=False)
    combined = combined.to_crs("EPSG:4326").sort_values("PostDist").reset_index(
        drop=True
    )
    if combined["PostDist"].duplicated().any():
        raise ValueError("Merged postcode boundaries contain duplicate districts")
    if combined.geometry.is_empty.any() or not combined.geometry.is_valid.all():
        raise ValueError("Merged postcode boundaries contain invalid geometry")
    return combined


def validate_topology(
    districts: gpd.GeoDataFrame,
    overlap_tolerance_m2: float = 1.0,
) -> dict[str, int | float]:
    """Reject positive-area overlaps between postcode district polygons."""
    metric = ensure_wgs84(districts).to_crs("EPSG:27700").reset_index(drop=True)
    overlap_pairs: list[tuple[str, str, float]] = []
    for left_index, left_row in metric.iterrows():
        candidate_indexes = metric.sindex.query(
            left_row.geometry,
            predicate="intersects",
        )
        for right_index in candidate_indexes:
            if right_index <= left_index:
                continue
            overlap_area = left_row.geometry.intersection(
                metric.iloc[right_index].geometry
            ).area
            if overlap_area > overlap_tolerance_m2:
                overlap_pairs.append(
                    (
                        left_row["PostDist"],
                        metric.iloc[right_index]["PostDist"],
                        float(overlap_area),
                    )
                )
    if overlap_pairs:
        largest = sorted(overlap_pairs, key=lambda item: item[2], reverse=True)[:10]
        raise ValueError(f"Postcode districts overlap by positive area: {largest}")
    return {
        "positiveAreaOverlapPairs": 0,
        "overlapToleranceM2": overlap_tolerance_m2,
    }


def validate_landmark_coverage(districts: gpd.GeoDataFrame) -> dict[str, str]:
    """Confirm that known Central London locations fall inside a district."""
    districts = ensure_wgs84(districts)
    coverage: dict[str, str] = {}
    for name, coordinates in LANDMARKS.items():
        point = Point(*coordinates)
        matches = districts[districts.geometry.covers(point)]["PostDist"].tolist()
        if len(matches) != 1:
            raise ValueError(
                f"{name} should be covered by one postcode district; found {matches}"
            )
        coverage[name] = matches[0]
    return coverage


def _write_atomically(data: gpd.GeoDataFrame, destination: Path) -> None:
    temporary = destination.with_name(f"{destination.stem}.tmp.gpkg")
    if temporary.exists():
        temporary.unlink()
    data.to_file(temporary, layer="districts", driver="GPKG", index=False)
    os.replace(temporary, destination)


def build(refresh: bool = False) -> None:
    units = fetch_central_postcode_units(refresh=refresh)
    central = dissolve_central_districts(units)
    current_postcodes = fetch_current_central_postcodes(refresh=refresh)
    current_validation = validate_current_postcodes(central, current_postcodes)
    districts = merge_with_baseline(central)
    topology_validation = validate_topology(districts)
    landmarks = validate_landmark_coverage(districts)

    _write_atomically(districts, OUTPUT_PATH)
    metadata = {
        "source": "Mixed GLA and GeoLytix postcode district boundary build",
        "sourceUrl": GLA_POSTCODE_UNIT_URL.rsplit("/query", 1)[0],
        "sources": [
            {
                "name": "Greater London Authority Postcode Units ArcGIS layer",
                "role": "EC, WC, W1 and SW1 postcode unit polygons",
                "url": GLA_POSTCODE_UNIT_URL.rsplit("/query", 1)[0],
                "licence": "Public ArcGIS service; confirm commercial reuse terms",
            },
            {
                "name": "GeoLytix postal boundaries 2012",
                "role": "Outer-London postcode district polygons",
                "url": "https://datashare.ed.ac.uk/handle/10283/2597",
                "licence": "Open Government Licence",
                "attribution": (
                    "Postal Boundaries (C) GeoLytix copyright and database right "
                    "2012; contains Ordnance Survey, Royal Mail and National "
                    "Statistics data (C) their respective 2012 rights holders"
                ),
            },
            {
                "name": "ONS live postcode centroids",
                "role": "February 2026 currentness validation",
                "url": ONS_LIVE_POSTCODE_URL.rsplit("/query", 1)[0],
                "licence": "Contains Ordnance Survey and ONS intellectual property",
            },
        ],
        "currentValidationSource": "ONS live postcode centroids",
        "currentValidationSourceUrl": ONS_LIVE_POSTCODE_URL.rsplit("/query", 1)[0],
        "currentValidationReferenceDate": ONS_POSTCODE_REFERENCE_DATE,
        "currentValidation": current_validation,
        "retrievedOn": date.today().isoformat(),
        "method": (
            "GLA postcode units dissolved for EC, WC, W1 and SW1; their "
            "footprint is subtracted from retained GeoLytix 2012 districts "
            "to prevent mixed-source overlaps"
        ),
        "centralDistrictCount": len(central),
        "districtCount": len(districts),
        "topologyValidation": topology_validation,
        "landmarkCoverage": landmarks,
    }
    SOURCE_METADATA_PATH.write_text(
        json.dumps(metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print(f"Fetched {len(units):,} current Central London postcode units")
    print(f"Dissolved to {len(central):,} Central London districts")
    print(
        "Validated against "
        f"{current_validation['postcodeCount']:,} live ONS postcode centroids"
    )
    print(f"Wrote {len(districts):,} London district boundaries to {OUTPUT_PATH}")
    print(f"Landmark coverage: {landmarks}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Ignore the local GLA postcode-unit cache.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    build(refresh=arguments.refresh)
