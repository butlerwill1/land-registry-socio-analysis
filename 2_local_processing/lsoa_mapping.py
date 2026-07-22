"""Utilities for mapping official 2021 LSOAs to postcode districts."""

from __future__ import annotations

import json
import os
import shutil
import urllib.parse
import urllib.request
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from local_utils import create_imd_column_mapping, indicators_to_aggregate


LSOA_FEATURE_SERVICE_URL = (
    "https://services-eu1.arcgis.com/EbKcOS6EXZroSyoi/arcgis/rest/services/"
    "LSOA_IMD2025_WGS84/FeatureServer/0/query"
)
IMD_2025_CSV_URL = (
    "https://assets.publishing.service.gov.uk/media/691ded56d140bbbaa59a2a7d/"
    "File_7_IoD2025_All_Ranks_Scores_Deciles_Population_Denominators.csv"
)

AREA_CRS = "EPSG:27700"
WEB_CRS = "EPSG:4326"
ARCGIS_BATCH_SIZE = 250
MINIMUM_SUMMARY_OVERLAP_SHARE = 0.5


def _request_json(
    url: str,
    params: dict[str, str | int],
    method: str = "GET",
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


def fetch_lsoa2021_for_bounds(
    bounds: tuple[float, float, float, float],
    cache_path: Path | None = None,
    refresh: bool = False,
) -> gpd.GeoDataFrame:
    """Fetch official 2021 LSOA polygons intersecting a WGS84 bounding box."""
    if cache_path is not None and cache_path.exists() and not refresh:
        cached = gpd.read_file(cache_path)
        return cached.to_crs(WEB_CRS)

    xmin, ymin, xmax, ymax = bounds
    envelope = f"{xmin},{ymin},{xmax},{ymax}"
    id_payload = _request_json(
        LSOA_FEATURE_SERVICE_URL,
        {
            "where": "1=1",
            "geometry": envelope,
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "returnIdsOnly": "true",
            "returnGeometry": "false",
            "f": "json",
        },
    )
    object_ids = sorted(id_payload.get("objectIds", []))
    if not object_ids:
        raise ValueError("The official LSOA service returned no IDs for the bounds")

    features: list[dict] = []
    for start in range(0, len(object_ids), ARCGIS_BATCH_SIZE):
        batch = object_ids[start : start + ARCGIS_BATCH_SIZE]
        payload = _request_json(
            LSOA_FEATURE_SERVICE_URL,
            {
                "objectIds": ",".join(str(object_id) for object_id in batch),
                "outFields": "LSOA21CD,LSOA21NM",
                "returnGeometry": "true",
                "outSR": "4326",
                "f": "geojson",
            },
            method="POST",
        )
        page = payload.get("features", [])
        features.extend(page)
        if len(page) != len(batch):
            raise ValueError(
                f"Expected {len(batch)} LSOAs from ArcGIS, received {len(page)}"
            )

    if not features:
        raise ValueError("The official LSOA service returned no features for the bounds")

    lsoas = gpd.GeoDataFrame.from_features(features, crs=WEB_CRS)
    lsoas = lsoas[["LSOA21CD", "LSOA21NM", "geometry"]]
    lsoas = lsoas.drop_duplicates(subset="LSOA21CD").reset_index(drop=True)

    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        lsoas.to_file(cache_path, driver="GeoJSON")

    return lsoas


def download_imd_2025_csv(
    destination: Path,
    refresh: bool = False,
) -> Path:
    """Download the corrected official IMD 2025 all-fields CSV."""
    if destination.exists() and not refresh:
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".download")
    request = urllib.request.Request(
        IMD_2025_CSV_URL,
        headers={"User-Agent": "land-registry-socio-analysis/1.0"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        with temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
    os.replace(temporary, destination)
    return destination


def load_imd_2025(csv_path: Path) -> pd.DataFrame:
    """Load and standardise the official IMD 2025 table."""
    imd = pd.read_csv(csv_path).rename(columns=create_imd_column_mapping())
    required = {
        "LSOACode",
        "AreaName",
        "LADCode",
        "LADName",
        "OverallScore",
        "OverallRank",
        "TotalPopulation",
    }
    missing = sorted(required - set(imd.columns))
    if missing:
        raise ValueError(f"IMD 2025 source is missing required columns: {missing}")
    if imd["LSOACode"].duplicated().any():
        raise ValueError("IMD 2025 source contains duplicate LSOA codes")
    return imd


def ensure_wgs84(geodata: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Return WGS84 data, repairing the known undefined district CRS metadata."""
    geodata = geodata.copy()
    if geodata.crs is None or geodata.crs.to_epsg() is None:
        xmin, ymin, xmax, ymax = geodata.total_bounds
        looks_like_lon_lat = -180 <= xmin <= xmax <= 180 and -90 <= ymin <= ymax <= 90
        if not looks_like_lon_lat:
            raise ValueError("Cannot infer the coordinate system from the geometry bounds")
        geodata = geodata.set_crs(WEB_CRS, allow_override=True)
    return geodata.to_crs(WEB_CRS)


def assign_lsoas_by_largest_overlap(
    lsoas: gpd.GeoDataFrame,
    districts: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Assign each LSOA to the postcode district covering its largest area share.

    All area calculations use British National Grid. The output retains the winning
    and runner-up overlap shares so ambiguous boundary assignments remain visible.
    """
    required_lsoa = {"LSOA21CD", "geometry"}
    required_district = {"PostDist", "geometry"}
    if missing := sorted(required_lsoa - set(lsoas.columns)):
        raise ValueError(f"LSOA data is missing required columns: {missing}")
    if missing := sorted(required_district - set(districts.columns)):
        raise ValueError(f"District data is missing required columns: {missing}")

    lsoas = ensure_wgs84(lsoas)
    districts = ensure_wgs84(districts)
    if lsoas["LSOA21CD"].duplicated().any():
        raise ValueError("LSOA codes must be unique before spatial assignment")
    if districts["PostDist"].duplicated().any():
        raise ValueError("Postcode districts must be unique before spatial assignment")

    lsoas_metric = lsoas.to_crs(AREA_CRS).copy()
    districts_metric = districts[["PostDist", "geometry"]].to_crs(AREA_CRS).copy()
    lsoas_metric["geometry"] = lsoas_metric.geometry.make_valid()
    districts_metric["geometry"] = districts_metric.geometry.make_valid()
    lsoas_metric["lsoa_area_m2"] = lsoas_metric.geometry.area

    candidates = gpd.sjoin(
        lsoas_metric,
        districts_metric,
        how="inner",
        predicate="intersects",
    )
    district_geometry = districts_metric.geometry
    candidates["district_geometry"] = candidates["index_right"].map(district_geometry)
    candidates["intersection_area_m2"] = candidates.apply(
        lambda row: row.geometry.intersection(row["district_geometry"]).area,
        axis=1,
    )
    candidates = candidates[candidates["intersection_area_m2"] > 0].copy()
    if candidates.empty:
        raise ValueError("No positive-area intersections were found")

    candidates["overlap_share"] = (
        candidates["intersection_area_m2"] / candidates["lsoa_area_m2"]
    ).clip(upper=1.0)
    candidates = candidates.sort_values(
        ["LSOA21CD", "overlap_share", "PostDist"],
        ascending=[True, False, True],
    )
    candidates["candidate_rank"] = candidates.groupby("LSOA21CD").cumcount() + 1

    best = candidates[candidates["candidate_rank"] == 1].copy()
    second = (
        candidates[candidates["candidate_rank"] == 2]
        .set_index("LSOA21CD")["overlap_share"]
        .rename("second_overlap_share")
    )
    best = best.join(second, on="LSOA21CD")
    best["second_overlap_share"] = best["second_overlap_share"].fillna(0.0)
    best["overlap_margin"] = best["overlap_share"] - best["second_overlap_share"]
    best["assignment_method"] = np.where(
        best["overlap_share"] >= 0.999,
        "fully_within",
        "largest_overlap",
    )
    best["assignment_confidence"] = pd.cut(
        best["overlap_share"],
        bins=[-np.inf, 0.6, 0.8, np.inf],
        labels=["low", "medium", "high"],
        right=False,
    ).astype(str)
    best["included_in_district_summary"] = (
        best["overlap_share"] >= MINIMUM_SUMMARY_OVERLAP_SHARE
    )

    assignment_columns = [
        "LSOA21CD",
        "PostDist",
        "overlap_share",
        "second_overlap_share",
        "overlap_margin",
        "assignment_method",
        "assignment_confidence",
        "included_in_district_summary",
    ]
    assigned = lsoas.merge(best[assignment_columns], on="LSOA21CD", how="inner")
    assigned = gpd.GeoDataFrame(assigned, geometry="geometry", crs=WEB_CRS)
    return assigned.sort_values("LSOA21CD").reset_index(drop=True)


def _weighted_average(group: pd.DataFrame, column: str) -> float:
    values = pd.to_numeric(group[column], errors="coerce")
    weights = pd.to_numeric(group["TotalPopulation"], errors="coerce")
    valid = values.notna() & weights.notna() & (weights > 0)
    if not valid.any():
        return float(values.mean())
    return float(np.average(values[valid], weights=weights[valid]))


def aggregate_lsoas_to_districts(
    assigned_lsoas: gpd.GeoDataFrame,
    districts: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Create population-weighted district summaries from assigned LSOAs."""
    districts = ensure_wgs84(districts)[["PostDist", "geometry"]].copy()
    district_area = districts.to_crs(AREA_CRS).geometry.area / 1_000_000
    districts["AreaKm2"] = district_area.to_numpy()
    district_lookup = districts.set_index("PostDist")

    rows: list[dict] = []
    for post_dist, assigned_group in assigned_lsoas.groupby("PostDist", sort=True):
        group = assigned_group[assigned_group["included_in_district_summary"]].copy()
        if group.empty:
            continue
        population = pd.to_numeric(group["TotalPopulation"], errors="coerce").sum()
        dependent_children = pd.to_numeric(
            group["DependentChildren"], errors="coerce"
        ).sum()
        population_60_plus = pd.to_numeric(
            group["Population60Plus"], errors="coerce"
        ).sum()
        working_age = pd.to_numeric(
            group["WorkingAgePopulation"], errors="coerce"
        ).sum()
        area_km2 = float(district_lookup.loc[post_dist, "AreaKm2"])

        row = {
            "PostDist": post_dist,
            "AreaName": ", ".join(sorted(group["LADName"].dropna().unique())),
            "LocalAuthorityCount": int(group["LADName"].nunique()),
            "CountLowLevelAreas": int(len(group)),
            "CandidateLowLevelAreas": int(len(assigned_group)),
            "ExcludedAmbiguousLSOAs": int(len(assigned_group) - len(group)),
            "FullyWithinLSOAs": int((group["assignment_method"] == "fully_within").sum()),
            "BoundaryCrossingLSOAs": int(
                (group["assignment_method"] == "largest_overlap").sum()
            ),
            "LowConfidenceLSOAs": int(
                (group["assignment_confidence"] == "low").sum()
            ),
            "MeanOverlapShare": round(float(group["overlap_share"].mean()), 4),
            "MinOverlapShare": round(float(group["overlap_share"].min()), 4),
            "AreaKm2": round(area_km2, 3),
            "TotalPopulation": int(population),
            "DependentChildren": int(dependent_children),
            "Population60Plus": int(population_60_plus),
            "WorkingAgePopulation": int(working_age),
            "DependentChildren%": round(dependent_children * 100 / population, 2),
            "Population60Plus%": round(population_60_plus * 100 / population, 2),
            "WorkingAgePopulation%": round(working_age * 100 / population, 2),
            "PopulationDensity": round(population / area_km2, 2),
            "geometry": district_lookup.loc[post_dist, "geometry"],
        }

        for indicator in indicators_to_aggregate:
            score_column = f"{indicator}Score"
            rank_column = f"{indicator}Rank"
            if score_column in group.columns:
                row[f"{indicator}Avg"] = round(
                    _weighted_average(group, score_column), 2
                )
            if rank_column in group.columns:
                row[f"{indicator}RankAvg"] = round(
                    _weighted_average(group, rank_column), 2
                )
        rows.append(row)

    aggregated = gpd.GeoDataFrame(rows, geometry="geometry", crs=WEB_CRS)
    return aggregated.sort_values("PostDist").reset_index(drop=True)
