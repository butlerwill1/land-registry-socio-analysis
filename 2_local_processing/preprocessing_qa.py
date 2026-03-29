"""
Data Quality Assurance for Land Registry and Geospatial Datasets
==================================================================

This script performs comprehensive quality assurance checks on:
    1. UK Land Registry property transaction data (CSV format)
    2. Postcode district polygon shapefiles
    3. Socio-economic indicator shapefiles (English IMD 2019)

QA Checks Include:
    - Missing value detection and quantification
    - Data type validation
    - Postcode format validation
    - Date range verification
    - Geometry validity checks
    - Postcode district consistency verification

Note: This script is designed for exploratory QA on local samples. For full 5GB
      dataset processing, use the PySpark scripts instead.

Author: Land Registry Analysis Project
"""

# ============================================================================
# IMPORTS
# ============================================================================
import pandas as pd
import regex as re
import matplotlib.pyplot as plt
import sys
import os
import importlib
import geopandas as gpd
from shapely.validation import explain_validity

# Import local utilities
sys.path.insert(0, os.path.dirname(__file__))
import local_utils as func

# Reload custom functions to pick up any changes
importlib.reload(func)


# ============================================================================
# SECTION 1: LAND REGISTRY DATA QUALITY CHECKS
# ============================================================================
print("="*70)
print("LAND REGISTRY DATA QA")
print("="*70)

# Load raw Land Registry CSV data
# Note: This is a sample for QA purposes. Full dataset should use PySpark.
print("\nLoading Land Registry data...")
land_registry_data = pd.read_csv("land_registry_data.csv")
print(f"Loaded {len(land_registry_data):,} transaction records")

# ----------------------------------------------------------------------------
# Check 1: Postcode Missing Values
# ----------------------------------------------------------------------------
print("\n--- Postcode Quality Check ---")
missing_postcodes = land_registry_data['postcode'].isna().sum()
print(f"Missing postcodes: {missing_postcodes:,} ({missing_postcodes/len(land_registry_data)*100:.2f}%)")

# Sample records with missing postcodes for manual inspection
if missing_postcodes > 0:
    print("\nSample of records with missing postcodes:")
    print(land_registry_data[land_registry_data['postcode'].isna()].sample(min(20, missing_postcodes)))
    print("Note: Missing postcodes cannot be geographically classified and will be excluded.")

# Filter to non-null postcodes for further validation
land_registry_data_notna = land_registry_data[land_registry_data['postcode'].notna()]

# ----------------------------------------------------------------------------
# Check 2: Postcode Format Validation
# ----------------------------------------------------------------------------
print("\n--- Postcode Format Validation ---")
# Valid UK postcodes should contain a space (e.g., "SW1A 1AA")
invalid_format = land_registry_data_notna[~land_registry_data_notna['postcode'].str.contains(" ")]
print(f"Postcodes without space character: {len(invalid_format)}")
if len(invalid_format) > 0:
    print("Invalid postcode values:")
    print(invalid_format['postcode'].unique())

# ----------------------------------------------------------------------------
# Check 3: Price Data Validation
# ----------------------------------------------------------------------------
print("\n--- Price Data Quality Check ---")
missing_prices = land_registry_data['price'].isna().sum()
print(f"Missing prices: {missing_prices}")

if missing_prices == 0:
    print("✓ All records have valid price data")
    print(f"  Price range: £{land_registry_data['price'].min():,.0f} - £{land_registry_data['price'].max():,.0f}")
    print(f"  Median price: £{land_registry_data['price'].median():,.0f}")

# ----------------------------------------------------------------------------
# Check 4: Date Validation
# ----------------------------------------------------------------------------
print("\n--- Date Transfer Quality Check ---")
print(f"Date range (raw): {land_registry_data['date_transfer'].min()} to {land_registry_data['date_transfer'].max()}")

# Convert to datetime and check for parsing errors
land_registry_data['date_transfer'] = pd.to_datetime(
    land_registry_data['date_transfer'],
    errors='coerce'
)

invalid_dates = land_registry_data['date_transfer'].isna().sum()
print(f"Invalid/unparseable dates: {invalid_dates}")

if invalid_dates == 0:
    print("✓ All dates successfully parsed")
    print(f"  Date range: {land_registry_data['date_transfer'].min().date()} to {land_registry_data['date_transfer'].max().date()}")


# ============================================================================
# SECTION 2: PYSPARK OUTPUT DATA QA
# ============================================================================
print("\n" + "="*70)
print("PYSPARK TRANSACTION GROUPBY OUTPUT QA")
print("="*70)

# Load the aggregated transaction data produced by PySpark processing
print("\nLoading district-level transaction groupby data...")
district_groupby = pd.read_csv("District_Transaction_Groupby.csv")
print(f"Loaded {len(district_groupby):,} district-level aggregations")

# ----------------------------------------------------------------------------
# Check 5: Postcode District Numbering Consistency
# ----------------------------------------------------------------------------
print("\n--- Postcode District Numbering Validation ---")
print("Checking that district numbers follow expected patterns (e.g., BR1, BR2, BR3)...")

unique_districts_transactions = district_groupby['postcode_district'].unique().tolist()
print(f"Found {len(unique_districts_transactions)} unique postcode districts")

# Use custom function to validate district numbering patterns
func.check_districts(unique_districts_transactions)


# ============================================================================
# SECTION 3: GEOSPATIAL DATA QA
# ============================================================================
print("\n" + "="*70)
print("GEOSPATIAL POLYGON DATA QA")
print("="*70)

# Load polygon shapefiles
print("\nLoading geospatial datasets...")
postcode_dist_poly = gpd.read_file("GB_Postcodes/PostalDistrict.shp")
socio_economic = gpd.read_file("English_IMD_2019/IMD_2019.shp")
print(f"  Postcode districts: {len(postcode_dist_poly):,} polygons")
print(f"  Socio-economic areas: {len(socio_economic):,} polygons")

# ----------------------------------------------------------------------------
# Check 6: Postcode District Consistency (Polygons)
# ----------------------------------------------------------------------------
print("\n--- Polygon Postcode District Validation ---")
unique_poly_districts = postcode_dist_poly['PostDist'].unique().tolist()
print(f"Found {len(unique_poly_districts)} unique districts in polygon data")

func.check_districts(unique_poly_districts)

# ----------------------------------------------------------------------------
# Check 7: Dataset Overlap Analysis
# ----------------------------------------------------------------------------
print("\n--- Transaction vs Polygon District Overlap ---")

# Districts in transactions but not in polygons (cannot be mapped)
missing_in_poly = [d for d in unique_districts_transactions if d not in unique_poly_districts]
print(f"Districts in transactions but NOT in polygon data: {len(missing_in_poly)}")
if len(missing_in_poly) > 0 and len(missing_in_poly) < 20:
    print(f"  {missing_in_poly}")

# Districts in polygons but not in transactions (no transaction data)
missing_in_trans = [d for d in unique_poly_districts if d not in unique_districts_transactions]
print(f"Districts in polygon data but NOT in transactions: {len(missing_in_trans)}")
if len(missing_in_trans) > 0 and len(missing_in_trans) < 20:
    print(f"  {missing_in_trans}")

# ----------------------------------------------------------------------------
# Check 8: Geometry Validity
# ----------------------------------------------------------------------------
print("\n--- Geometry Validity Check ---")

invalid_postcode_geometries = postcode_dist_poly[~postcode_dist_poly.is_valid]
invalid_socio_geometries = socio_economic[~socio_economic.is_valid]

print(f"Invalid postcode geometries: {len(invalid_postcode_geometries)}")
print(f"Invalid socio-economic geometries: {len(invalid_socio_geometries)}")

if len(invalid_socio_geometries) > 0:
    print("\nInvalid geometry details:")
    for index, row in invalid_socio_geometries.iterrows():
        explanation = explain_validity(row.geometry)
        print(f"  Row {index}: {explanation}")

# ----------------------------------------------------------------------------
# Fix: Repair Invalid Geometries
# ----------------------------------------------------------------------------
if len(invalid_postcode_geometries) > 0 or len(invalid_socio_geometries) > 0:
    print("\n--- Repairing Invalid Geometries ---")
    print("Using buffer(0) method to fix self-intersections...")

    # Apply buffer(0) to fix topology issues (common fix for self-intersections)
    postcode_dist_poly['geometry'] = postcode_dist_poly.apply(
        lambda x: x.geometry.buffer(0) if not x.geometry.is_valid else x.geometry,
        axis=1
    )

    socio_economic['geometry'] = socio_economic.apply(
        lambda x: x.geometry.buffer(0) if not x.geometry.is_valid else x.geometry,
        axis=1
    )

    # Verify repairs
    still_invalid_postcode = postcode_dist_poly[~postcode_dist_poly.is_valid]
    still_invalid_socio = socio_economic[~socio_economic.is_valid]

    print(f"  Postcode geometries still invalid: {len(still_invalid_postcode)}")
    print(f"  Socio-economic geometries still invalid: {len(still_invalid_socio)}")

    # Save repaired shapefiles
    if len(still_invalid_postcode) == 0 and len(still_invalid_socio) == 0:
        print("\n✓ All geometries successfully repaired. Saving updated shapefiles...")
        postcode_dist_poly.to_file("GB_Postcodes/PostalDistrict.shp")
        socio_economic.to_file("English_IMD_2019/IMD_2019.shp")
        print("  ✓ Saved GB_Postcodes/PostalDistrict.shp")
        print("  ✓ Saved English_IMD_2019/IMD_2019.shp")
    else:
        print("\n⚠ Some geometries could not be automatically repaired. Manual inspection required.")

print("\n" + "="*70)
print("QA COMPLETE")
print("="*70)
