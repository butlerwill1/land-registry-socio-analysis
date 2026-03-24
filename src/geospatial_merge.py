"""
Geospatial Merge: Property Transactions + Socio-Economic Indicators
====================================================================

This script performs spatial joins to merge UK Land Registry transaction data with
socio-economic indicators from the English Indices of Multiple Deprivation (IMD) 2019.

Process Overview:
    1. Load postcode district polygons and socio-economic LSOA polygons
    2. Calculate area metrics and standardize coordinate systems
    3. Perform spatial joins (LSOA within postcode districts)
    4. Aggregate socio-economic indicators to postcode district level
    5. Merge with transaction groupby data
    6. Export final dataset for Streamlit visualization

Geographic Hierarchy:
    - LSOA (Lower Layer Super Output Area): ~1,500 people, fine-grained socio-economic data
    - Postcode District: Broader area (e.g., "SW1A"), transaction aggregation level

Output Files:
    - socio_economic_postcode.gpkg: LSOA-level data with postcode district mapping
    - district_groupby_socio_economic.gpkg: Final merged dataset for visualization

Author: Land Registry Analysis Project
"""

# ============================================================================
# IMPORTS
# ============================================================================
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import src.functions as func
import importlib
import os

# Reload custom functions to pick up any changes
importlib.reload(func)


# ============================================================================
# SECTION 1: LOAD AND PREPARE POSTCODE DISTRICT POLYGONS
# ============================================================================
print("="*70)
print("GEOSPATIAL MERGE: TRANSACTIONS + SOCIO-ECONOMIC DATA")
print("="*70)

print("\n--- Loading Postcode District Polygons ---")
postcode_dist_poly = gpd.read_file("GB_Postcodes/PostalDistrict.shp")
print(f"Loaded {len(postcode_dist_poly):,} postcode district polygons")
print(f"Original CRS: {postcode_dist_poly.crs}")

# Calculate area in square kilometers
postcode_dist_poly['AreaKm2'] = postcode_dist_poly.geometry.area / 1_000_000

# Convert to WGS84 (EPSG:4326) for consistency with web mapping standards
postcode_dist_poly = postcode_dist_poly.to_crs("EPSG:4326")
print(f"Converted to CRS: EPSG:4326 (WGS84)")

# Preserve geometry column for later merging after aggregation
postcode_dist_poly['postcode_dist_geometry'] = postcode_dist_poly.geometry


# ============================================================================
# SECTION 2: LOAD AND PREPARE SOCIO-ECONOMIC DATA
# ============================================================================
print("\n--- Loading Socio-Economic Indicator Data (IMD 2019) ---")
socio_economic = gpd.read_file("English_IMD_2019/IMD_2019.shp")
print(f"Loaded {len(socio_economic):,} LSOA (Lower Layer Super Output Area) polygons")
print(f"Original CRS: {socio_economic.crs}")

# Rename abbreviated column names to human-readable format
# Note: IMD 2019 uses cryptic abbreviations (e.g., "IncScore" → "IncomeScore")
print("\nRenaming columns from abbreviations to full names...")
renaming_dict = {col: func.clean_socio_columns(col) for col in socio_economic.columns}
renaming_dict['lsoa11nmw'] = 'AreaName'

socio_economic = socio_economic.rename(columns=renaming_dict)
socio_economic = socio_economic.rename(columns={'OverallRank0': 'OverallRank'})

# Convert to WGS84 for consistency
socio_economic = socio_economic.to_crs("EPSG:4326")
print(f"Converted to CRS: EPSG:4326 (WGS84)")

# IMD 2019 Scoring Note:
# - Rank 1 = Most deprived area
# - Higher scores = Higher deprivation
# - Example: High crime score = High crime rate



# ============================================================================
# SECTION 3: SPATIAL JOINS
# ============================================================================
print("\n--- Performing Spatial Joins ---")

# Join 1: LSOAs within postcode districts (for aggregation)
# Using 'within' predicate: LSOA polygon must be completely inside postcode district
print("  1. Joining LSOAs to postcode districts (inner join for aggregation)...")
postcode_socio_economic = gpd.sjoin(
    socio_economic,
    postcode_dist_poly,
    how='inner',
    predicate='within'
)
print(f"     Matched {len(postcode_socio_economic):,} LSOAs to postcode districts")

# Join 2: Preserve all LSOAs with postcode district mapping (for granular analysis)
# Using 'left' join: Keep all LSOAs even if they don't fall within a postcode district
print("  2. Joining LSOAs to postcode districts (left join for granular data)...")
socio_economic_postcode = gpd.sjoin(
    socio_economic,
    postcode_dist_poly,
    how='left',
    predicate='within'
)
print(f"     Preserved all {len(socio_economic_postcode):,} LSOAs")

# Export granular LSOA-level data with postcode district mapping
print("\n  Exporting LSOA-level data with postcode mapping...")
socio_economic_postcode.drop(columns=['postcode_dist_geometry']) \
    .to_file("socio_economic_postcode.gpkg", layer='socio', driver="GPKG")
print("  ✓ Saved: socio_economic_postcode.gpkg")


# ============================================================================
# SECTION 4: AGGREGATE SOCIO-ECONOMIC DATA TO POSTCODE DISTRICT LEVEL
# ============================================================================
print("\n--- Aggregating Socio-Economic Indicators to District Level ---")
print("  Averaging LSOA indicators within each postcode district...")

# Custom aggregation function calculates weighted averages and statistics
aggregated_data = postcode_socio_economic.groupby("PostDist") \
    .apply(func.postcode_socio_grouby_agg) \
    .reset_index()

print(f"  Created aggregated data for {len(aggregated_data):,} postcode districts")


# ============================================================================
# SECTION 5: MERGE WITH TRANSACTION DATA
# ============================================================================
print("\n--- Merging Transaction Data with Socio-Economic Indicators ---")

# Load transaction groupby data (output from PySpark processing)
print("  Loading transaction groupby data...")
district_transaction_groupby = pd.read_csv("District_Transaction_Groupby%.csv")
print(f"  Loaded {len(district_transaction_groupby):,} transaction records")

# Merge on postcode district
print("  Performing merge on postcode_district...")
district_groupby_socio_economic = pd.merge(
    district_transaction_groupby,
    aggregated_data,
    how='left',
    left_on='postcode_district',
    right_on='PostDist'
)
print(f"  Merged dataset contains {len(district_groupby_socio_economic):,} records")

# Convert back to GeoDataFrame (geometry was lost during pandas merge)
district_groupby_socio_economic_gdf = gpd.GeoDataFrame(
    district_groupby_socio_economic,
    geometry='geometry'
)


# ============================================================================
# SECTION 6: FILTER AND EXPORT FINAL DATASET
# ============================================================================
print("\n--- Filtering and Exporting Final Dataset ---")

# Filter to most recent year (2023) for visualization
# Remove records with missing or unknown postcode districts
print("  Filtering to year 2023 and valid postcode districts...")
district_groupby_socio_economic_gdf = district_groupby_socio_economic_gdf[
    (district_groupby_socio_economic_gdf['PostDist'].notna()) &
    (district_groupby_socio_economic_gdf['year'] == 2023) &
    (district_groupby_socio_economic_gdf['PostDist'] != 'Unknown')
]
print(f"  Filtered to {len(district_groupby_socio_economic_gdf):,} records for 2023")

# Export final merged dataset
print("\n  Exporting final merged dataset...")
district_groupby_socio_economic_gdf.drop(columns=['Unnamed: 0'], errors='ignore') \
    .to_file("district_groupby_socio_economic.gpkg", layer='socio', driver="GPKG")

file_size_mb = round(os.path.getsize("district_groupby_socio_economic.gpkg") / 1_000_000, 2)
print(f"  ✓ Saved: district_groupby_socio_economic.gpkg ({file_size_mb} MB)")

print("\n" + "="*70)
print("GEOSPATIAL MERGE COMPLETE")
print("="*70)
print(f"\nFinal dataset ready for Streamlit visualization:")
print(f"  - {len(district_groupby_socio_economic_gdf):,} postcode districts")
print(f"  - Year: 2023")
print(f"  - File: district_groupby_socio_economic.gpkg")


# ============================================================================
# OPTIONAL: EXPLORATORY ANALYSIS (COMMENTED OUT)
# ============================================================================
# Uncomment the sections below for exploratory data analysis

# # Sample Graph 1: Population Density vs Transaction Volume
# test = district_groupby_socio_economic[
#     (district_groupby_socio_economic['is_london?'] != 'Outside London') &
#     (district_groupby_socio_economic['property_type'] == 'F')
# ]
# plt.figure(figsize=(10, 6))
# plt.title("Population Density vs Number of Transactions (London Flats)")
# plt.xlabel("Population Density (people/km²)")
# plt.ylabel("Number of Transactions")
# plt.scatter(test['PopulationDensity'], test['num_transactions'], alpha=0.6)
# plt.show()

# # Sample Graph 2: LSOA Count vs Area Size
# plt.figure(figsize=(10, 6))
# plt.title("Number of LSOAs vs Postcode District Area")
# plt.xlabel("Count of Lower-Level Areas (LSOAs)")
# plt.ylabel("Area (km²)")
# plt.scatter(test['CountLowLevelAreas'], test['AreaKm2'], alpha=0.6)
# plt.show()