"""
Geospatial Merge: Property Transactions + Socio-Economic Indicators
====================================================================

This script performs spatial joins to merge UK Land Registry transaction data with
socio-economic indicators from the English Indices of Multiple Deprivation (IMD)
combined with population statistics.

Process Overview:
    1. Load postcode district polygons
    2. Load LSOA polygons and IMD_population_all_indices.csv data
    3. Join polygons with IMD data to create socio_economic GeoDataFrame
    4. Standardize coordinate systems
    5. Perform spatial joins (LSOA within postcode districts)
    6. Aggregate socio-economic indicators to postcode district level
    7. Merge with transaction groupby data
    8. Export final dataset for Streamlit visualization

Input Files:
    - 2_local_processing/1_bronze/Postal_District_Polygons/PostalDistrict.shp
    - 2_local_processing/1_bronze/Lower_layer_Super_Output_Areas_Dec_2011_polygons/LSOA_2011_EW_BFC_V3.shp
    - 2_local_processing/1_bronze/IMD_population_all_indices.csv

Geographic Hierarchy:
    - LSOA (Lower Layer Super Output Area): ~1,500 people, fine-grained socio-economic data
    - Postcode District: Broader area (e.g., "SW1A"), transaction aggregation level

Output Files:
    - socio_economic_postcode.gpkg: LSOA-level data with postcode district mapping
    - district_groupby_socio_economic.gpkg: Final merged dataset for visualization

Author: Land Registry Analysis Project
"""

#%% ============================================================================
# IMPORTS
# ============================================================================
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import sys
import os
import importlib

# Import local utilities
# Add the 2_local_processing directory to the Python path
project_root = os.path.abspath('.')
local_processing_dir = os.path.join(project_root, '2_local_processing')

# Try multiple possible locations
possible_paths = [
    local_processing_dir,  # If we're at project root
    project_root,  # If we're already in 2_local_processing
    os.path.dirname(os.path.abspath('.'))  # If we're in a subdirectory
]

# Add all possible paths
for path in possible_paths:
    if path not in sys.path:
        sys.path.insert(0, path)
    local_utils_path = os.path.join(path, 'local_utils.py')
    if os.path.exists(local_utils_path):
        print(f"Found local_utils.py at: {local_utils_path}")
        break

import local_utils as func

# Reload custom functions to pick up any changes
importlib.reload(func)


#%% ============================================================================
# SECTION 1: LOAD AND PREPARE POSTCODE DISTRICT POLYGONS
# ============================================================================
print("="*70)
print("GEOSPATIAL MERGE: TRANSACTIONS + SOCIO-ECONOMIC DATA")
print("="*70)

print("\n--- Loading Postcode District Polygons ---")
postcode_dist_poly = gpd.read_file("2_local_processing/1_bronze/Postal_District_Polygons/PostalDistrict.shp")
print(f"Loaded {len(postcode_dist_poly):,} postcode district polygons")
print(f"Original CRS: {postcode_dist_poly.crs}")

# Calculate area in square kilometers
# IMPORTANT: Calculate area BEFORE converting CRS!
# The original CRS (likely EPSG:27700 - British National Grid) uses meters as units,
# making area calculations accurate. After converting to EPSG:4326 (lat/lon degrees),
# area calculations would be distorted because degrees are not uniform distances.
postcode_dist_poly['AreaKm2'] = postcode_dist_poly.geometry.area / 1_000_000

# Convert to WGS84 (EPSG:4326) for consistency with web mapping standards
# See detailed CRS explanation in Section 2 below
postcode_dist_poly = postcode_dist_poly.to_crs("EPSG:4326")
print(f"Converted to CRS: EPSG:4326 (WGS84)")

# Preserve geometry column for later merging after aggregation
postcode_dist_poly['postcode_dist_geometry'] = postcode_dist_poly.geometry


#%% ============================================================================
# SECTION 2: LOAD AND PREPARE SOCIO-ECONOMIC DATA
# ============================================================================
print("\n--- Loading Socio-Economic Indicator Data (IMD with Population) ---")

# Load LSOA polygons
socio_economic_polygons = gpd.read_file("2_local_processing/1_bronze/Lower_layer_Super_Output_Areas_Dec_2011_polygons/LSOA_2011_EW_BFC_V3.shp")
print(f"Loaded {len(socio_economic_polygons):,} LSOA (Lower Layer Super Output Area) polygons")
print(f"Original CRS: {socio_economic_polygons.crs}")

# Load IMD + Population data
imd_population = pd.read_csv("2_local_processing/1_bronze/IMD_population_all_indices.csv")
print(f"Loaded {len(imd_population):,} rows from IMD_population_all_indices.csv")

# Rename columns from the CSV to match the expected naming convention
print("\nRenaming columns to standardized format...")
renaming_dict = func.create_imd_column_mapping()
imd_population = imd_population.rename(columns=renaming_dict)

# Join the polygons with the IMD data
print("\nJoining polygons with IMD data on LSOA code...")
socio_economic = socio_economic_polygons.merge(
    imd_population,
    left_on='LSOA11CD',
    right_on='LSOACode',
    how='inner'
)
print(f"Successfully joined {len(socio_economic):,} LSOA areas with IMD data")

# Convert to WGS84 for consistency with web mapping standards
#
# CRS (Coordinate Reference System) defines how geographic coordinates map to locations on Earth.
# Different CRS use different:
# - Projections: Methods to flatten the 3D Earth onto a 2D map
# - Units: Some use meters, others use degrees
# - Datum: Reference points for measuring positions on Earth's surface
#
# Common CRS codes:
# - EPSG:27700 (British National Grid): UK-specific, uses meters, optimized for accurate UK measurements
# - EPSG:4326 (WGS84): Global standard, uses latitude/longitude in degrees, used by GPS and web maps
#
# Why convert to EPSG:4326?
# 1. Web mapping compatibility: Leaflet, Folium, and most web maps expect WGS84
# 2. Consistency: All datasets in this project use the same CRS for joining
# 3. Interoperability: Makes it easy to overlay with other global datasets
#
# Note: For spatial calculations (area, distance), British National Grid is more accurate for UK data,
# but we already calculated AreaKm2 before converting, so we get the best of both worlds.
socio_economic = socio_economic.to_crs("EPSG:4326")
print(f"Converted to CRS: EPSG:4326 (WGS84)")

# IMD Scoring Note:
# - Rank 1 = Most deprived area
# - Higher scores = Higher deprivation
# - Example: High crime score = High crime rate



#%% ============================================================================
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

# Create output directory if it doesn't exist
# Use absolute path to ensure we write to the correct location
output_dir = os.path.join(os.path.abspath('.'), '2_local_processing', '2_silver')
os.makedirs(output_dir, exist_ok=True)

output_path = os.path.join(output_dir, "socio_economic_postcode.gpkg")
print(f"  Writing to: {output_path}")
socio_economic_postcode.drop(columns=['postcode_dist_geometry']) \
    .to_file(output_path, layer='socio', driver="GPKG")
print(f"  ✓ Saved: {output_path}")


#%% ============================================================================
# SECTION 4: AGGREGATE SOCIO-ECONOMIC DATA TO POSTCODE DISTRICT LEVEL
# ============================================================================
print("\n--- Aggregating Socio-Economic Indicators to District Level ---")
print("  Averaging LSOA indicators within each postcode district...")

# Custom aggregation function calculates weighted averages and statistics
district_socio_economic_aggregated = postcode_socio_economic.groupby("PostDist") \
    .apply(func.postcode_socio_grouby_agg) \
    .reset_index()

print(f"  Created aggregated data for {len(district_socio_economic_aggregated):,} postcode districts")

# Create output directory if it doesn't exist
# Use absolute path to ensure we write to the correct location
output_dir = os.path.join(os.path.abspath('.'), '2_local_processing', '3_gold')
os.makedirs(output_dir, exist_ok=True)

# Save the aggregated socio-economic data to gold layer
aggregated_output_path = os.path.join(output_dir, "district_socio_economic_aggregated.csv")
print(f"\n  Exporting aggregated socio-economic data...")
print(f"  Writing to: {aggregated_output_path}")
district_socio_economic_aggregated.drop(columns=['geometry'], errors='ignore').to_csv(aggregated_output_path, index=False)
print(f"  ✓ Saved: {aggregated_output_path}")


#%% ============================================================================
# SECTION 5: MERGE WITH TRANSACTION DATA
# ============================================================================
print("\n--- Merging Transaction Data with Socio-Economic Indicators ---")

# Load transaction groupby data (output from PySpark processing)
print("  Loading transaction groupby data...")
district_transaction_groupby = pd.read_csv("1_spark_processing/3_gold/district_transaction_groupby.csv")
print(f"  Loaded {len(district_transaction_groupby):,} transaction records")

# Merge on postcode district
print("  Performing merge on postcode_district...")
district_transaction_with_socio_economic = pd.merge(
    district_transaction_groupby,
    district_socio_economic_aggregated,
    how='left',
    left_on='postcode_district',
    right_on='PostDist'
)
print(f"  Merged dataset contains {len(district_transaction_with_socio_economic):,} records")

# Convert back to GeoDataFrame (geometry was lost during pandas merge)
district_transaction_with_socio_economic_gdf = gpd.GeoDataFrame(
    district_transaction_with_socio_economic,
    geometry='geometry'
)


#%% ============================================================================
# SECTION 6: FILTER AND EXPORT FINAL DATASET
# ============================================================================
print("\n--- Filtering and Exporting Final Dataset ---")

# Remove records with missing or unknown postcode districts
print("  Filtering to valid postcode districts...")
district_transactions_with_socio = district_transaction_with_socio_economic_gdf[
    (district_transaction_with_socio_economic_gdf['PostDist'].notna()) &
    (district_transaction_with_socio_economic_gdf['PostDist'] != 'Unknown')
]
print(f"  Filtered to {len(district_transactions_with_socio):,} records")

# Export final merged dataset
print("\n  Exporting final merged dataset...")

# Write to 2_local_processing/3_gold directory
gold_output_dir = os.path.join(os.path.abspath('.'), '2_local_processing', '3_gold')
os.makedirs(gold_output_dir, exist_ok=True)

final_output_path = os.path.join(gold_output_dir, "district_transactions_with_socio_economic.gpkg")
print(f"  Writing to: {final_output_path}")

district_transactions_with_socio.drop(columns=['Unnamed: 0'], errors='ignore') \
    .to_file(final_output_path, layer='socio', driver="GPKG")

file_size_mb = round(os.path.getsize(final_output_path) / 1_000_000, 2)
print(f"  ✓ Saved: {final_output_path} ({file_size_mb} MB)")

print("\n" + "="*70)
print("GEOSPATIAL MERGE COMPLETE")
print("="*70)
print(f"\nFinal dataset ready for Streamlit visualization:")
print(f"  - {len(district_transactions_with_socio):,} records")
print(f"  - File: {final_output_path}")


#%% ============================================================================
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