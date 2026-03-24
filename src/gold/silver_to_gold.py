"""
Land Registry Transaction Groupby Analysis
===========================================

This script performs comprehensive groupby aggregations on UK Land Registry property
transaction data using PySpark. It processes large-scale transaction data stored in
Parquet format on S3, enriches it with postcode classifications, and generates
statistical summaries at multiple geographic levels (area, district, sector).

Key Operations:
    1. Load transaction data from S3 Parquet files
    2. Parse and classify UK postcodes into geographic hierarchies
    3. Identify London vs non-London properties
    4. Calculate price statistics (mean, median, percentiles, variance)
    5. Compute year-over-year percentage changes
    6. Evaluate sample quality using statistical thresholds
    7. Export results to S3 as CSV files

Output Files:
    - area_pct_change.csv: Aggregated by postcode area
    - district_pct_change.csv: Aggregated by postcode district
    - sector_pct_change.csv: Aggregated by postcode sector

Author: Land Registry Analysis Project
"""

# ============================================================================
# IMPORTS
# ============================================================================
from pyspark.sql import SparkSession
from pyspark.sql.functions import udf, col, avg, count, expr, year, lag, when
from pyspark.sql.types import StringType, StructType, StructField
from pyspark.sql.window import Window
import re
import sys
import os

# Add parent directory to path to import pyspark_functions from same directory
# This works both locally and on EMR when using --py-files
try:
    import pyspark_functions as func
except ImportError:
    # Fallback for local development
    sys.path.insert(0, os.path.dirname(__file__))
    import pyspark_functions as func

import importlib

# Reload custom functions module to pick up any changes during development
importlib.reload(func)


# ============================================================================
# CONFIGURATION
# ============================================================================

# Sample quality thresholds for filtering unreliable aggregations
# These parameters help identify statistically robust property price samples
SAMPLE_QUALITY_PARAMS = {
    'min_transactions': 30,              # Minimum sample size (Central Limit Theorem)
    'max_coef_var': 50,                  # Maximum coefficient of variation (%)
    'max_median_mean_diff_pct': 10,      # Max median-mean difference (%) - detects skewness
    'max_iqr_pct': 25                    # Max IQR as % of median - another skewness measure
}

# S3 paths
PARQUET_INPUT_PATH = "s3a://landregistryproject/silver/land_registry_data.parquet"
OUTPUT_BASE_PATH = "s3a://landregistryproject/gold/"


# ============================================================================
# SPARK SESSION INITIALIZATION
# ============================================================================
spark = SparkSession.builder \
    .appName("LandRegistryGroupByAnalysis") \
    .getOrCreate()


# ============================================================================
# DATA LOADING AND INITIAL CLEANING
# ============================================================================
print("Loading Land Registry data from S3...")
df = spark.read.parquet(PARQUET_INPUT_PATH)

# Remove records with missing postcodes (cannot be geographically classified)
df = df.dropna(subset=['postcode'])
print(f"Loaded {df.count():,} transactions with valid postcodes")


# ============================================================================
# POSTCODE PARSING AND GEOGRAPHIC CLASSIFICATION
# ============================================================================

# Define schema for postcode parsing UDF output
# UK postcodes split into: Area (e.g., "SW"), District (e.g., "SW1A"), Sector (e.g., "SW1A-1")
split_output_schema = StructType([
    StructField("postcode_area", StringType(), True),
    StructField("postcode_district", StringType(), True),
    StructField("postcode_sector", StringType(), True)
])

# Register UDF to split postcodes into geographic components
split_postcode_udf = udf(func.split_postcode, split_output_schema)

print("Parsing postcodes into area, district, and sector...")
df = df.withColumn("postcode_parts", split_postcode_udf(df["postcode"]))
df = df.select("*", "postcode_parts.*")  # Flatten struct into separate columns

# Classify postcodes as Central London, Greater London, or Outside London
classify_postcode_london_udf = udf(func.classify_london_postcode, StringType())
df = df.withColumn("is_london?", classify_postcode_london_udf(
    df['postcode_area'],
    df['postcode_district']
))

# Convert date string to timestamp and extract year
df = df.withColumn("date_transfer", col("date_transfer").cast("timestamp"))
df = df.withColumn("year", year(col("date_transfer")))

print("Postcode parsing complete.")


# ============================================================================
# AGGREGATION: CALCULATE PRICE STATISTICS BY GEOGRAPHIC LEVEL
# ============================================================================

# Common grouping columns for all aggregations
groupby_cols = ['is_london?', 'property_type', 'year']

print("\nPerforming aggregations at multiple geographic levels...")

# Aggregate by postcode AREA (broadest level, e.g., "SW", "E", "M")
print("  - Aggregating by postcode area...")
area_groupby_df = func.groupby_calc_price(df, ['postcode_area'] + groupby_cols)
print(f"    Created {area_groupby_df.count():,} area-level aggregations")

# Aggregate by postcode DISTRICT (medium level, e.g., "SW1A", "E1", "M1")
print("  - Aggregating by postcode district...")
district_groupby_df = func.groupby_calc_price(
    df,
    ['postcode_area', 'postcode_district'] + groupby_cols
)
print(f"    Created {district_groupby_df.count():,} district-level aggregations")

# Aggregate by postcode SECTOR (finest level, e.g., "SW1A-1", "E1-6")
print("  - Aggregating by postcode sector...")
sector_groupby_df = func.groupby_calc_price(
    df,
    ['postcode_area', 'postcode_district', 'postcode_sector'] + groupby_cols
)
print(f"    Created {sector_groupby_df.count():,} sector-level aggregations")


# ============================================================================
# CALCULATE YEAR-OVER-YEAR PERCENTAGE CHANGES
# ============================================================================

print("\nCalculating year-over-year percentage changes...")

area_pct_change = func.calculate_pct_change(
    area_groupby_df,
    ['postcode_area'] + groupby_cols
)

district_pct_change = func.calculate_pct_change(
    district_groupby_df,
    ['postcode_district'] + groupby_cols
)

sector_pct_change = func.calculate_pct_change(
    sector_groupby_df,
    ['postcode_sector'] + groupby_cols
)

# Display sample results
print("\nSample results (Area level):")
area_pct_change.show(10)


# ============================================================================
# EVALUATE SAMPLE QUALITY
# ============================================================================

print("\nEvaluating sample quality using statistical thresholds...")

area_pct_change = func.evaluate_sample_quality(
    area_pct_change,
    SAMPLE_QUALITY_PARAMS
)

district_pct_change = func.evaluate_sample_quality(
    district_pct_change,
    SAMPLE_QUALITY_PARAMS
)

sector_pct_change = func.evaluate_sample_quality(
    sector_pct_change,
    SAMPLE_QUALITY_PARAMS
)

# Show quality statistics
good_samples_area = area_pct_change.filter(col("is_good_sample") == True).count()
total_samples_area = area_pct_change.count()
print(f"Area level: {good_samples_area:,} / {total_samples_area:,} samples passed quality checks")


# ============================================================================
# EXPORT RESULTS TO S3
# ============================================================================

print("\nExporting results to S3...")

# Coalesce to single file for easier downstream processing
# Note: For very large datasets, consider partitioning instead

area_pct_change.coalesce(1) \
    .write.format("csv") \
    .option("header", "true") \
    .mode("overwrite") \
    .save(f"{OUTPUT_BASE_PATH}area_pct_change.csv")
print("  ✓ Exported area_pct_change.csv")

district_pct_change.coalesce(1) \
    .write.format("csv") \
    .option("header", "true") \
    .mode("overwrite") \
    .save(f"{OUTPUT_BASE_PATH}district_pct_change.csv")
print("  ✓ Exported district_pct_change.csv")

sector_pct_change.coalesce(1) \
    .write.format("csv") \
    .option("header", "true") \
    .mode("overwrite") \
    .save(f"{OUTPUT_BASE_PATH}sector_pct_change.csv")
print("  ✓ Exported sector_pct_change.csv")

print("\n" + "="*70)
print("PROCESSING COMPLETE")
print("="*70)

# Stop Spark session
spark.stop()