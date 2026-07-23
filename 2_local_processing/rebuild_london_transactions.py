"""Rebuild London flat transaction aggregates directly from S3 silver data."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import boto3
import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow.fs as pafs
import pyarrow.parquet as pq


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SPARK_GOLD_DIR = PROJECT_ROOT / "1_spark_processing" / "3_gold"
if str(SPARK_GOLD_DIR) not in sys.path:
    sys.path.insert(0, str(SPARK_GOLD_DIR))

from postcode_utils import classify_london_postcode, split_postcode  # noqa: E402


AWS_REGION = "eu-west-2"
S3_BUCKET = "landregistryproject"
S3_PREFIX = "silver/land_registry_data.parquet/"

GOLD_DIR = PROJECT_ROOT / "2_local_processing" / "3_gold"
BOUNDARY_PATH = GOLD_DIR / "postcode_district_boundaries_london.gpkg"
TRANSACTION_OUTPUT = GOLD_DIR / "district_transactions_london_flats.csv"
PROPERTY_TYPE_OUTPUT = GOLD_DIR / "property_type_groupby_london_flats.csv"
PRICE_GRAPH_OUTPUT = GOLD_DIR / "district_groupby_price_graph_london_flats.csv"
SOURCE_METADATA_OUTPUT = GOLD_DIR / "london_transaction_source.json"

OUTWARD_PATTERN = r"^[A-Z]{1,2}\d[A-Z0-9]?$"
PARTITION_KEY_PATTERN = re.compile(
    r"^silver/land_registry_data\.parquet/year=(\d{4})/[^/]+\.parquet$"
)
QUALITY_THRESHOLDS = {
    "min_transactions": 30,
    "max_coef_var": 50,
    "max_median_mean_diff_pct": 10,
    "max_iqr_pct": 25,
}


def list_silver_parquet_objects() -> list[dict]:
    """List the versioned, year-partitioned silver Parquet objects."""
    client = boto3.client("s3", region_name=AWS_REGION)
    paginator = client.get_paginator("list_objects_v2")
    objects: list[dict] = []
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=S3_PREFIX):
        objects.extend(
            item
            for item in page.get("Contents", [])
            if item["Key"].endswith(".parquet")
        )
    objects.sort(key=lambda item: item["Key"])
    if not objects:
        raise ValueError(f"No Parquet files found at s3://{S3_BUCKET}/{S3_PREFIX}")
    unexpected = [
        item["Key"]
        for item in objects
        if PARTITION_KEY_PATTERN.fullmatch(item["Key"]) is None
    ]
    if unexpected:
        raise ValueError(f"Unexpected objects in silver dataset: {unexpected}")
    return objects


def _normalise_postcodes(frame: pd.DataFrame) -> pd.DataFrame:
    postcodes = frame["postcode"].astype("string").str.strip().str.upper()
    outward = postcodes.str.split().str[0]
    valid = outward.str.fullmatch(OUTWARD_PATTERN, na=False)
    frame = frame.loc[valid].copy()
    frame["postcode_district"] = outward.loc[valid]
    frame["postcode_area"] = frame["postcode_district"].map(
        lambda district: split_postcode(district)[0]
    )
    return frame


def load_london_flat_transactions(keys: list[str]) -> pd.DataFrame:
    """Stream flat transactions from S3 and retain mapped London districts."""
    district_codes = set(
        gpd.read_file(BOUNDARY_PATH, layer="districts")["PostDist"].astype(str)
    )
    filesystem = pafs.S3FileSystem(region=AWS_REGION)
    chunks: list[pd.DataFrame] = []

    for index, key in enumerate(keys, start=1):
        table = pq.read_table(
            f"{S3_BUCKET}/{key}",
            filesystem=filesystem,
            columns=[
                "transaction_id",
                "price",
                "date_transfer",
                "postcode",
                "property_type",
            ],
            filters=[("property_type", "=", "F")],
        )
        chunk = _normalise_postcodes(table.to_pandas())
        chunk = chunk[chunk["postcode_district"].isin(district_codes)].copy()
        if not chunk.empty:
            chunk["year"] = pd.to_datetime(chunk["date_transfer"]).dt.year
            chunks.append(
                chunk[
                    [
                        "postcode_area",
                        "postcode_district",
                        "transaction_id",
                        "year",
                        "price",
                        "date_transfer",
                    ]
                ]
            )
        if index % 10 == 0 or index == len(keys):
            retained = sum(len(item) for item in chunks)
            print(f"Read {index}/{len(keys)} Parquet files; retained {retained:,} flats")

    if not chunks:
        raise ValueError("No London flat transactions matched the district boundaries")
    transactions = pd.concat(chunks, ignore_index=True)
    transactions["price"] = pd.to_numeric(transactions["price"], errors="raise")
    validate_unique_transactions(transactions)
    return transactions


def validate_unique_transactions(transactions: pd.DataFrame) -> None:
    """Fail rather than silently double-count an overlapping S3 source build."""
    if transactions["transaction_id"].isna().any():
        raise ValueError("London flat transactions contain missing transaction IDs")
    duplicate_mask = transactions["transaction_id"].duplicated(keep=False)
    if duplicate_mask.any():
        duplicate_count = int(transactions.loc[duplicate_mask, "transaction_id"].nunique())
        examples = (
            transactions.loc[duplicate_mask, "transaction_id"]
            .drop_duplicates()
            .head(10)
            .tolist()
        )
        raise ValueError(
            "S3 silver data contains duplicate transaction IDs: "
            f"{duplicate_count:,} IDs; examples={examples}"
        )


def source_manifest_hash(source_objects: list[dict]) -> str:
    """Create a stable fingerprint for the exact S3 objects used in the build."""
    manifest = [
        {
            "key": item["Key"],
            "etag": str(item.get("ETag", "")).strip('"'),
            "size": int(item["Size"]),
        }
        for item in source_objects
    ]
    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def aggregate_transactions(transactions: pd.DataFrame) -> pd.DataFrame:
    """Calculate exact district-year price statistics and quality fields."""
    group_columns = ["postcode_area", "postcode_district", "year"]
    grouped = transactions.groupby(group_columns, sort=True)["price"]
    summary = grouped.agg(
        num_transactions="count",
        avg_price="mean",
        stddev_price="std",
        skewness_price="skew",
    )
    summary["kurtosis_price"] = grouped.agg(pd.Series.kurt)

    quantiles = grouped.quantile([0.25, 0.5, 0.75, 0.90, 0.95]).unstack()
    quantiles.columns = [
        "25th_percentile_price",
        "median_price",
        "75th_percentile_price",
        "90th_percentile_price",
        "95th_percentile_price",
    ]
    summary = summary.join(quantiles).reset_index()

    one_decimal_columns = [
        "avg_price",
        "stddev_price",
        "25th_percentile_price",
        "median_price",
        "75th_percentile_price",
        "90th_percentile_price",
        "95th_percentile_price",
    ]
    summary[one_decimal_columns] = summary[one_decimal_columns].round(1)
    summary[["skewness_price", "kurtosis_price"]] = summary[
        ["skewness_price", "kurtosis_price"]
    ].round(2)

    summary["coef_var"] = (
        summary["stddev_price"] * 100 / summary["avg_price"]
    ).round(1)
    summary["iqr"] = (
        summary["75th_percentile_price"] - summary["25th_percentile_price"]
    ).round(1)
    summary["median_mean_diff"] = (
        summary["median_price"] - summary["avg_price"]
    ).round(1)
    summary["median_mean_diff_pct"] = (
        summary["median_mean_diff"].abs() * 100 / summary["median_price"]
    ).round(1)
    summary["iqr_pct"] = (summary["iqr"] * 100 / summary["median_price"]).round(1)

    summary["PostDist"] = summary["postcode_district"]
    summary["is_london?"] = summary.apply(
        lambda row: classify_london_postcode(
            row["postcode_area"],
            row["postcode_district"],
        ),
        axis=1,
    )
    summary["property_type"] = "F"

    summary = summary.sort_values(["postcode_district", "year"]).reset_index(drop=True)
    district_group = summary.groupby("postcode_district", sort=False)
    summary["lag_median_price"] = district_group["median_price"].shift(1)
    summary["median_pct_change_1_year"] = (
        (summary["median_price"] - summary["lag_median_price"])
        * 100
        / summary["lag_median_price"]
    ).round(1)
    summary["roll_median_pct_2_year"] = district_group[
        "median_pct_change_1_year"
    ].transform(lambda values: values.rolling(2, min_periods=1).mean()).round(1)
    summary["roll_median_pct_5_year"] = district_group[
        "median_pct_change_1_year"
    ].transform(lambda values: values.rolling(5, min_periods=1).mean()).round(1)
    summary[
        [
            "lag_median_price",
            "median_pct_change_1_year",
            "roll_median_pct_2_year",
            "roll_median_pct_5_year",
        ]
    ] = summary[
        [
            "lag_median_price",
            "median_pct_change_1_year",
            "roll_median_pct_2_year",
            "roll_median_pct_5_year",
        ]
    ].fillna(0)

    summary["is_good_sample"] = (
        (summary["num_transactions"] >= QUALITY_THRESHOLDS["min_transactions"])
        & (summary["coef_var"] <= QUALITY_THRESHOLDS["max_coef_var"])
        & (
            summary["median_mean_diff_pct"]
            <= QUALITY_THRESHOLDS["max_median_mean_diff_pct"]
        )
        & (summary["iqr_pct"] <= QUALITY_THRESHOLDS["max_iqr_pct"])
    )

    output_columns = [
        "postcode_area",
        "postcode_district",
        "PostDist",
        "is_london?",
        "property_type",
        "year",
        "num_transactions",
        "avg_price",
        "stddev_price",
        "25th_percentile_price",
        "median_price",
        "75th_percentile_price",
        "90th_percentile_price",
        "95th_percentile_price",
        "skewness_price",
        "kurtosis_price",
        "coef_var",
        "iqr",
        "median_mean_diff",
        "median_mean_diff_pct",
        "iqr_pct",
        "lag_median_price",
        "median_pct_change_1_year",
        "roll_median_pct_2_year",
        "roll_median_pct_5_year",
        "is_good_sample",
    ]
    return summary[output_columns]


def _write_csv_atomically(frame: pd.DataFrame, destination: Path) -> None:
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    frame.to_csv(temporary, index=False)
    os.replace(temporary, destination)


def write_outputs(
    transactions: pd.DataFrame,
    summary: pd.DataFrame,
    source_objects: list[dict],
) -> None:
    """Write dashboard-compatible transaction outputs and source metadata."""
    _write_csv_atomically(summary, TRANSACTION_OUTPUT)

    property_types = (
        summary.groupby("postcode_district", as_index=False)["num_transactions"]
        .sum()
        .assign(property_type="Flat")
    )
    property_types = property_types[
        ["postcode_district", "property_type", "num_transactions"]
    ]
    _write_csv_atomically(property_types, PROPERTY_TYPE_OUTPUT)

    price_graph = summary[
        [
            "postcode_district",
            "year",
            "avg_price",
            "median_price",
            "num_transactions",
        ]
    ].rename(columns={"median_price": "50th_percentile_price"})
    _write_csv_atomically(price_graph, PRICE_GRAPH_OUTPUT)

    latest_date = pd.to_datetime(transactions["date_transfer"]).max().date()
    metadata = {
        "source": "HM Land Registry Price Paid Data, validated silver layer",
        "sourcePath": f"s3://{S3_BUCKET}/{S3_PREFIX}",
        "generatedOn": date.today().isoformat(),
        "latestTransferDate": latest_date.isoformat(),
        "sourceParquetFileCount": len(source_objects),
        "sourceManifestSha256": source_manifest_hash(source_objects),
        "districtCount": int(summary["postcode_district"].nunique()),
        "transactionCount": int(summary["num_transactions"].sum()),
        "years": [
            int(summary["year"].min()),
            int(summary["year"].max()),
        ],
        "latestCompleteYear": min(
            int(summary["year"].max()),
            date.today().year - 1,
        ),
        "aggregation": "Exact flat-price statistics by postcode district and year",
    }
    SOURCE_METADATA_OUTPUT.write_text(
        json.dumps(metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print(f"Wrote {len(summary):,} district-year rows")
    print(f"Covered {metadata['districtCount']:,} postcode districts")
    print(f"Aggregated {metadata['transactionCount']:,} flat transactions")
    print(f"Latest transfer date: {metadata['latestTransferDate']}")


def rebuild() -> None:
    source_objects = list_silver_parquet_objects()
    keys = [item["Key"] for item in source_objects]
    transactions = load_london_flat_transactions(keys)
    summary = aggregate_transactions(transactions)
    write_outputs(transactions, summary, source_objects)


def parse_args() -> argparse.Namespace:
    return argparse.ArgumentParser(description=__doc__).parse_args()


if __name__ == "__main__":
    parse_args()
    rebuild()
