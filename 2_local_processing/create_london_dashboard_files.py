"""
Create London Dashboard Data Files
===================================

This script filters the main geospatial datasets to include only London data
and creates two sets of output files:
1. London Flats only - for Streamlit dashboard
2. London All Property Types - for future Django app

Input Files (from 2_local_processing/3_gold/ and 2_silver/):
    - district_transactions_with_socio_economic.gpkg
    - socio_economic_postcode.gpkg

Output Files (to 2_local_processing/3_gold/):

    London Flats (for Streamlit):
    - district_transactions_with_socio_economic_london_flats.gpkg
    - socio_economic_postcode_london_flats.gpkg
    - property_type_groupby_london_flats.csv (will only contain Flats)
    - district_groupby_price_graph_london_flats.csv

    London All Property Types (for Django):
    - district_transactions_with_socio_economic_london.gpkg
    - socio_economic_postcode_london.gpkg
    - property_type_groupby_london.csv
    - district_groupby_price_graph_london.csv

Author: Land Registry Analysis Project
"""

#%% ============================================================================
# IMPORTS
# ============================================================================
import pandas as pd
import geopandas as gpd
import os
import sys

# Add the 2_local_processing directory to path for local_utils
project_root = os.path.abspath('.')
local_processing_dir = os.path.join(project_root, '2_local_processing')
if local_processing_dir not in sys.path:
    sys.path.insert(0, local_processing_dir)

print("="*70)
print("CREATE LONDON DASHBOARD DATA FILES")
print("="*70)


#%% ============================================================================
# SECTION 1: DEFINE PATHS
# ============================================================================
print("\n--- Setting up paths ---")

# Input paths
silver_dir = os.path.join(local_processing_dir, '2_silver')
gold_dir = os.path.join(local_processing_dir, '3_gold')

input_district_transactions = os.path.join(gold_dir, 'district_transactions_with_socio_economic.gpkg')
input_socio_postcode = os.path.join(silver_dir, 'socio_economic_postcode.gpkg')

# Output paths - London All Property Types (for Django)
output_district_transactions_london = os.path.join(gold_dir, 'district_transactions_with_socio_economic_london.gpkg')
output_socio_postcode_london = os.path.join(gold_dir, 'socio_economic_postcode_london.gpkg')
output_property_type_groupby = os.path.join(gold_dir, 'property_type_groupby_london.csv')
output_price_graph = os.path.join(gold_dir, 'district_groupby_price_graph_london.csv')

# Output paths - London Flats Only (for Streamlit)
# OPTIMIZED: Split into geometry file (GPKG) + transaction time-series (CSV) to reduce file size
output_district_geometry_london_flats = os.path.join(gold_dir, 'district_geometry_london_flats.gpkg')
output_district_transactions_london_flats = os.path.join(gold_dir, 'district_transactions_london_flats.csv')
output_socio_postcode_london_flats = os.path.join(gold_dir, 'socio_economic_postcode_london_flats.gpkg')
output_property_type_groupby_flats = os.path.join(gold_dir, 'property_type_groupby_london_flats.csv')
output_price_graph_flats = os.path.join(gold_dir, 'district_groupby_price_graph_london_flats.csv')

print(f"  Input directory (silver): {silver_dir}")
print(f"  Input/Output directory (gold): {gold_dir}")


#%% ============================================================================
# SECTION 2: LOAD MAIN DATASETS
# ============================================================================
print("\n--- Loading main datasets ---")

print(f"  Loading district transactions with socio-economic data...")
district_transactions = gpd.read_file(input_district_transactions, layer='socio')
print(f"  Loaded {len(district_transactions):,} records")

print(f"  Loading LSOA-level socio-economic data...")
socio_postcode = gpd.read_file(input_socio_postcode, layer='socio')
print(f"  Loaded {len(socio_postcode):,} LSOA areas")


#%% ============================================================================
# SECTION 3: FILTER FOR LONDON DATA
# ============================================================================
print("\n--- Filtering for London data ---")

# Filter district transactions for London (all property types)
# Use the 'is_london?' column which identifies Central/Greater London
print("  Filtering district transactions for London (all property types)...")
district_transactions_london = district_transactions[
    district_transactions['is_london?'].isin(['Central London', 'Greater London'])
].copy()
print(f"  Filtered to {len(district_transactions_london):,} London records (all property types)")

# Year filter removed - keeping all years in the dataset

# Filter district transactions for London Flats only
print("  Filtering district transactions for London Flats...")
district_transactions_london_flats = district_transactions[
    (district_transactions['is_london?'].isin(['Central London', 'Greater London'])) &
    (district_transactions['property_type'] == 'F')
].copy()
print(f"  Filtered to {len(district_transactions_london_flats):,} London Flat records")

# Year filter removed - keeping all years in the dataset

# Get unique London postcode districts (from all property types)
london_districts = district_transactions_london['PostDist'].unique()
print(f"  Found {len(london_districts)} unique London postcode districts")

# Get unique London postcode districts (from flats only)
london_districts_flats = district_transactions_london_flats['PostDist'].unique()
print(f"  Found {len(london_districts_flats)} unique London postcode districts with flats")

# Filter LSOA-level socio-economic data for London districts (all property types)
print("  Filtering LSOA socio-economic data for London (all property types)...")
socio_postcode_london = socio_postcode[
    socio_postcode['PostDist'].isin(london_districts)
].copy()
print(f"  Filtered to {len(socio_postcode_london):,} London LSOA areas")

# Filter LSOA-level socio-economic data for London districts (flats only)
print("  Filtering LSOA socio-economic data for London (flats)...")
socio_postcode_london_flats = socio_postcode[
    socio_postcode['PostDist'].isin(london_districts_flats)
].copy()
print(f"  Filtered to {len(socio_postcode_london_flats):,} London LSOA areas (districts with flats)")


#%% ============================================================================
# SECTION 3.5: REDUCE FLATS DATASET SIZE FOR STREAMLIT
# ============================================================================
print("\n--- Reducing Flats dataset size for Streamlit (removing Min/Max/Median columns) ---")

# Define the 8 socio-economic indicators that have Min/Max/Median columns
indicators_to_aggregate = ['Overall', 'Income', 'Employment', 'Education',
                           'Health', 'Crime', 'HousingBarriers', 'Environment']

# Build list of columns to drop (Median, Min, Max for each indicator)
columns_to_drop = []
for indicator in indicators_to_aggregate:
    columns_to_drop.extend([
        f'{indicator}Median',
        f'{indicator}Min',
        f'{indicator}Max'
    ])

# Drop columns from Flats datasets (keeping only Avg and RankAvg)
print(f"  Dropping {len(columns_to_drop)} columns from Flats datasets...")
print(f"  Columns to drop: {', '.join(columns_to_drop[:8])}... (and {len(columns_to_drop)-8} more)")

# Drop from district transactions flats
original_cols = len(district_transactions_london_flats.columns)
district_transactions_london_flats = district_transactions_london_flats.drop(
    columns=[col for col in columns_to_drop if col in district_transactions_london_flats.columns],
    errors='ignore'
)
dropped_count = original_cols - len(district_transactions_london_flats.columns)
print(f"  ✓ Dropped {dropped_count} columns from district_transactions_london_flats")

# Drop from socio postcode flats (LSOA level doesn't have aggregated columns, so this may drop 0)
original_cols = len(socio_postcode_london_flats.columns)
socio_postcode_london_flats = socio_postcode_london_flats.drop(
    columns=[col for col in columns_to_drop if col in socio_postcode_london_flats.columns],
    errors='ignore'
)
dropped_count = original_cols - len(socio_postcode_london_flats.columns)
print(f"  ✓ Dropped {dropped_count} columns from socio_postcode_london_flats")

print(f"  Final Flats dataset has {len(district_transactions_london_flats.columns)} columns (vs {len(district_transactions_london.columns)} in full dataset)")


#%% ============================================================================
# SECTION 4: EXPORT FILTERED GEOPACKAGES
# ============================================================================
print("\n--- Exporting filtered GeoPackages ---")

print(f"\n  Exporting London All Property Types (for Django)...")
print(f"    Writing {output_district_transactions_london}...")
district_transactions_london.to_file(output_district_transactions_london, layer='socio', driver='GPKG')
file_size_mb = round(os.path.getsize(output_district_transactions_london) / 1_000_000, 2)
print(f"    ✓ Saved ({file_size_mb} MB)")

print(f"    Writing {output_socio_postcode_london}...")
socio_postcode_london.to_file(output_socio_postcode_london, layer='socio', driver='GPKG')
file_size_mb = round(os.path.getsize(output_socio_postcode_london) / 1_000_000, 2)
print(f"    ✓ Saved ({file_size_mb} MB)")

print(f"\n  Exporting London Flats Only (for Streamlit - OPTIMIZED SPLIT FILES)...")

# Step 1: Create geometry-only file (one row per district)
print(f"    Creating district geometry file (one row per district)...")
# Store the CRS before grouping
original_crs = district_transactions_london_flats.crs

district_geometry_flats = district_transactions_london_flats.groupby('PostDist').first().reset_index()

# Keep only: PostDist, geometry, and static socio-economic columns (no yearly data)
geometry_columns = ['PostDist', 'geometry', 'AreaName', 'CountLowLevelAreas', 'AreaKm2',
                   'TotalPopulation', 'DependentChildren', 'Population60Plus', 'WorkingAgePopulation',
                   'DependentChildren%', 'Population60Plus%', 'WorkingAgePopulation%', 'PopulationDensity',
                   'OverallAvg', 'OverallRankAvg', 'IncomeAvg', 'IncomeRankAvg',
                   'EmploymentAvg', 'EmploymentRankAvg', 'EducationAvg', 'EducationRankAvg',
                   'HealthAvg', 'HealthRankAvg', 'CrimeAvg', 'CrimeRankAvg',
                   'HousingBarriersAvg', 'HousingBarriersRankAvg', 'EnvironmentAvg', 'EnvironmentRankAvg']

district_geometry_flats = district_geometry_flats[geometry_columns]

# Convert back to GeoDataFrame and restore CRS
district_geometry_flats = gpd.GeoDataFrame(district_geometry_flats, geometry='geometry', crs=original_crs)

print(f"    Writing {output_district_geometry_london_flats}...")
district_geometry_flats.to_file(output_district_geometry_london_flats, layer='socio', driver='GPKG')
file_size_mb = round(os.path.getsize(output_district_geometry_london_flats) / 1_000_000, 2)
print(f"    ✓ Saved geometry file: {len(district_geometry_flats)} districts ({file_size_mb} MB)")

# Step 2: Create CSV with yearly transaction data (NO geometry)
print(f"    Creating transaction time-series CSV (no geometry)...")
# Keep all columns EXCEPT geometry and the static socio-economic columns
transaction_columns = ['postcode_area', 'postcode_district', 'PostDist', 'is_london?', 'property_type',
                      'year', 'num_transactions', 'avg_price', 'stddev_price',
                      '25th_percentile_price', 'median_price', '75th_percentile_price',
                      '90th_percentile_price', '95th_percentile_price', 'skewness_price',
                      'kurtosis_price', 'coef_var', 'iqr', 'median_mean_diff',
                      'median_mean_diff_pct', 'iqr_pct', 'lag_median_price',
                      'median_pct_change_1_year', 'roll_median_pct_2_year',
                      'roll_median_pct_5_year', 'is_good_sample']

district_transactions_csv = district_transactions_london_flats[transaction_columns].copy()
print(f"    Writing {output_district_transactions_london_flats}...")
district_transactions_csv.to_csv(output_district_transactions_london_flats, index=False)
file_size_mb = round(os.path.getsize(output_district_transactions_london_flats) / 1_000_000, 2)
print(f"    ✓ Saved transaction CSV: {len(district_transactions_csv)} rows ({file_size_mb} MB)")

# Step 3: Export LSOA socio-economic data (unchanged)
print(f"    Writing {output_socio_postcode_london_flats}...")
socio_postcode_london_flats.to_file(output_socio_postcode_london_flats, layer='socio', driver='GPKG')
file_size_mb_socio = round(os.path.getsize(output_socio_postcode_london_flats) / 1_000_000, 2)
print(f"    ✓ Saved LSOA socio-economic file ({file_size_mb_socio} MB)")

total_size_mb = round(
    os.path.getsize(output_district_geometry_london_flats) / 1_000_000 +
    os.path.getsize(output_district_transactions_london_flats) / 1_000_000,
    2
)
print(f"\n    FILE SIZE OPTIMIZATION SUMMARY:")
print(f"      Old approach: ~129 MB (single GPKG with duplicated geometry)")
print(f"      New approach: ~{total_size_mb} MB (geometry GPKG + transaction CSV)")
print(f"      Reduction: {round((1 - total_size_mb/129) * 100, 1)}%")


#%% ============================================================================
# SECTION 5: CREATE PROPERTY TYPE GROUPBY CSV
# ============================================================================
print("\n--- Creating property type groupby CSV ---")

# Map property type codes to human-readable names
prop_type_dict = {
    'T': 'Terraced',
    'S': 'Semi-Detached',
    'D': 'Detached',
    'F': 'Flat',
    'O': 'Other'
}

# Create London All Property Types aggregation
print("  Creating property type aggregation for London (all property types)...")
london_for_aggregation = district_transactions_london.copy()
london_for_aggregation['property_type_name'] = london_for_aggregation['property_type'].map(prop_type_dict)

# Aggregate: group by postcode district and property type, sum transactions
# Note: This aggregates across ALL years, not just a single year
property_type_groupby = london_for_aggregation.groupby(
    ['postcode_district', 'property_type_name']
)['num_transactions'].sum().reset_index()

# Rename columns - keep lowercase with underscore to match data pipeline naming
property_type_groupby.columns = ['postcode_district', 'property_type', 'num_transactions']

# Export to CSV
print(f"    Writing {output_property_type_groupby}...")
property_type_groupby.to_csv(output_property_type_groupby, index=False)
print(f"    ✓ Saved ({len(property_type_groupby):,} records)")

# Create London Flats Only aggregation
print("  Creating property type aggregation for London (flats only)...")
london_flats_for_aggregation = district_transactions_london_flats.copy()
london_flats_for_aggregation['property_type_name'] = london_flats_for_aggregation['property_type'].map(prop_type_dict)

# Aggregate: group by postcode district and property type, sum transactions
property_type_groupby_flats = london_flats_for_aggregation.groupby(
    ['postcode_district', 'property_type_name']
)['num_transactions'].sum().reset_index()

# Rename columns
property_type_groupby_flats.columns = ['postcode_district', 'property_type', 'num_transactions']

# Export to CSV
print(f"    Writing {output_property_type_groupby_flats}...")
property_type_groupby_flats.to_csv(output_property_type_groupby_flats, index=False)
print(f"    ✓ Saved ({len(property_type_groupby_flats):,} records)")


#%% ============================================================================
# SECTION 6: CREATE PRICE GRAPH CSV
# ============================================================================
print("\n--- Creating price graph CSV ---")

# Select columns needed for time-series price visualization
# These are used by the Streamlit chart showing price changes over time
price_graph_cols = ['postcode_district', 'year', 'avg_price', '50th_percentile_price', 'num_transactions']

# Create London All Property Types price graph
print("  Creating price graph for London (all property types)...")
missing_cols = [col for col in price_graph_cols if col not in district_transactions_london.columns]
if missing_cols:
    print(f"  WARNING: Missing columns: {missing_cols}")
    print(f"  Available columns: {list(district_transactions_london.columns)}")
    # Use available columns
    available_cols = [col for col in price_graph_cols if col in district_transactions_london.columns]
    price_graph = district_transactions_london[available_cols].copy()
else:
    price_graph = district_transactions_london[price_graph_cols].copy()

# Drop any duplicate rows (shouldn't be any, but just in case)
price_graph = price_graph.drop_duplicates()

# Export to CSV
print(f"    Writing {output_price_graph}...")
price_graph.to_csv(output_price_graph, index=False)
print(f"    ✓ Saved ({len(price_graph):,} records)")

# Create London Flats Only price graph
print("  Creating price graph for London (flats only)...")
missing_cols_flats = [col for col in price_graph_cols if col not in district_transactions_london_flats.columns]
if missing_cols_flats:
    print(f"  WARNING: Missing columns: {missing_cols_flats}")
    print(f"  Available columns: {list(district_transactions_london_flats.columns)}")
    # Use available columns
    available_cols = [col for col in price_graph_cols if col in district_transactions_london_flats.columns]
    price_graph_flats = district_transactions_london_flats[available_cols].copy()
else:
    price_graph_flats = district_transactions_london_flats[price_graph_cols].copy()

# Drop any duplicate rows
price_graph_flats = price_graph_flats.drop_duplicates()

# Export to CSV
print(f"    Writing {output_price_graph_flats}...")
price_graph_flats.to_csv(output_price_graph_flats, index=False)
print(f"    ✓ Saved ({len(price_graph_flats):,} records)")


#%% ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "="*70)
print("LONDON DASHBOARD FILES CREATED")
print("="*70)

print("\n" + "="*70)
print("LONDON ALL PROPERTY TYPES (for Django app):")
print("="*70)
print(f"  1. {output_district_transactions_london}")
print(f"     - {len(district_transactions_london):,} London transaction records")
print(f"\n  2. {output_socio_postcode_london}")
print(f"     - {len(socio_postcode_london):,} London LSOA areas")
print(f"\n  3. {output_property_type_groupby}")
print(f"     - {len(property_type_groupby):,} property type aggregations")
print(f"\n  4. {output_price_graph}")
print(f"     - {len(price_graph):,} price time-series records")

print("\n" + "="*70)
print("LONDON FLATS ONLY (for Streamlit dashboard):")
print("="*70)
print(f"  1. {output_district_transactions_london_flats}")
print(f"     - {len(district_transactions_london_flats):,} London Flat transaction records")
print(f"\n  2. {output_socio_postcode_london_flats}")
print(f"     - {len(socio_postcode_london_flats):,} London LSOA areas (districts with flats)")
print(f"\n  3. {output_property_type_groupby_flats}")
print(f"     - {len(property_type_groupby_flats):,} property type aggregations (Flats only)")
print(f"\n  4. {output_price_graph_flats}")
print(f"     - {len(price_graph_flats):,} price time-series records (Flats only)")

print("\n" + "="*70)
print(f"All files saved to: {gold_dir}")
print("="*70)
print("\nStreamlit dashboard: Use the *_flats.gpkg and *_flats.csv files")
print("Django app: Use the non-flats versions (all property types)")



# %%
