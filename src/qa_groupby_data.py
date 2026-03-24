"""
QA and Preparation of PySpark Groupby Output Data
==================================================

This script performs quality assurance and data preparation on the transaction groupby
data produced by PySpark processing. It prepares the data for downstream geospatial
merging and Streamlit visualization.

Key Operations:
    1. Load and enrich PySpark output with derived fields
    2. Filter low-quality samples (insufficient transaction counts)
    3. Calculate 5-year rolling average price changes
    4. Sort by price increase for easy identification of hotspots
    5. Remove unnecessary columns to reduce file size
    6. Export cleaned datasets for visualization pipeline

Output Files:
    - District_Transaction_Groupby%.csv: Main dataset for geospatial merge
    - district_groupby_price_graph.csv: Lightweight time-series data for charts
    - property_type_groupby.csv: Transaction counts by property type

Author: Land Registry Analysis Project
"""

# ============================================================================
# IMPORTS
# ============================================================================
import pandas as pd
import regex as re
import matplotlib.pyplot as plt
import src.functions as func
import importlib

# Reload custom functions to pick up any changes
importlib.reload(func)


# ============================================================================
# SECTION 1: LOAD AND ENRICH DATA
# ============================================================================
print("="*70)
print("QA AND PREPARATION OF PYSPARK GROUPBY OUTPUT")
print("="*70)

print("\n--- Loading PySpark Output ---")
district_groupby = pd.read_csv("District_Transaction_Groupby%.csv")
print(f"Loaded {len(district_groupby):,} records")

# Extract postcode area from district (e.g., "SW1A" → "SW")
print("\n--- Enriching Data ---")
district_groupby['postcode_area'] = district_groupby['postcode_district'].apply(
    lambda x: re.sub(r'[^A-Za-z]', '', x)
)

# Map property type codes to human-readable names
prop_type_dict = {
    'T': 'Terraced',
    'S': 'Semi-Detached',
    'D': 'Detached',
    'F': 'Flat',
    'O': 'Other'
}
district_groupby['property_type'] = district_groupby['property_type'].map(prop_type_dict)
print(f"  ✓ Mapped property types: {list(prop_type_dict.values())}")

# Export property type summary for 2023
print("\n--- Creating Property Type Summary ---")
property_type_groupby = district_groupby[district_groupby['year'] == 2023] \
    .groupby(['postcode_district', 'property_type'])['num_transactions'] \
    .sum() \
    .reset_index()
property_type_groupby.to_csv("property_type_groupby.csv", index=False)
print(f"  ✓ Saved property_type_groupby.csv ({len(property_type_groupby):,} records)")


# ============================================================================
# SECTION 2: FILTERING AND QUALITY CONTROL
# ============================================================================
print("\n--- Applying Filters ---")

# Filter 1: Focus on Flats (can be changed to other property types)
print("  Filtering to property type: Flat")
district_groupby = district_groupby[district_groupby['property_type'] == 'Flat']
print(f"    Remaining records: {len(district_groupby):,}")

# Optional Filter 2: Geographic region (uncomment to use)
# print("  Filtering to London areas only...")
# district_groupby = district_groupby[district_groupby['is_london?'] != 'Outside London']

# Optional Filter 3: Year range (uncomment to use)
# print("  Filtering to years >= 2010...")
# district_groupby = district_groupby[district_groupby['year'] >= 2010]

# Filter 4: Remove districts with insufficient recent transaction data
print("\n--- Removing Low-Volume Districts ---")
num_transactions_threshold = 60
print(f"  Threshold: {num_transactions_threshold} transactions (for years >= 2018)")

districts_below_threshold = district_groupby[
    (district_groupby['num_transactions'] <= num_transactions_threshold) &
    (district_groupby['year'] >= 2018)
]['postcode_district'].unique().tolist()

print(f"  Districts below threshold: {len(districts_below_threshold)}")

district_groupby = district_groupby[
    ~district_groupby['postcode_district'].isin(districts_below_threshold)
]
print(f"  Remaining records after filter: {len(district_groupby):,}")


# ============================================================================
# SECTION 3: CALCULATE 5-YEAR ROLLING AVERAGE FOR SORTING
# ============================================================================
print("\n--- Calculating 5-Year Rolling Average Price Changes ---")

# Extract 2023 rolling average for each district
perc_price_rise_2023 = district_groupby[district_groupby['year'] == 2023][
    ['postcode_district', 'property_type', 'rolling_avg_median_pct_change_5_year']
].rename(columns={'rolling_avg_median_pct_change_5_year': '5YearAvg%PriceInc'})

print(f"  Calculated 5-year averages for {len(perc_price_rise_2023):,} districts")

# Merge back onto main dataset for sorting
district_groupby = pd.merge(
    district_groupby,
    perc_price_rise_2023,
    on=['postcode_district', 'property_type']
)

# Sort by 5-year price increase (descending), then by district and year
print("\n--- Sorting Data ---")
district_groupby.sort_values(
    ['5YearAvg%PriceInc', 'postcode_district', 'year'],
    ascending=[False, True, False],
    inplace=True
)
print("  ✓ Sorted by 5-year price increase (highest first)")


# ============================================================================
# SECTION 4: EXPORT CLEANED DATASETS
# ============================================================================
print("\n--- Exporting Cleaned Datasets ---")

# Remove columns not needed for downstream processing
cols_to_remove = [
    'coef_var', 'iqr', 'median_mean_diff', 'median_mean_diff_pct',
    'iqr_pct', 'lag_median_price', 'median_pct_change_1_year',
    'rolling_avg_median_pct_change_2_year', 'is_good_sample'
]

district_groupby.drop(columns=cols_to_remove, errors='ignore') \
    .to_csv("District_Transaction_Groupby%.csv", index=False)
print("  ✓ Saved District_Transaction_Groupby%.csv (for geospatial merge)")

# Create lightweight dataset for time-series charts
cols_for_graph = [
    'postcode_district', 'is_london?', 'property_type', 'year',
    'num_transactions', 'avg_price', '50th_percentile_price'
]

district_groupby_price_graph = district_groupby[cols_for_graph]
district_groupby_price_graph.to_csv("district_groupby_price_graph.csv", index=False)
print("  ✓ Saved district_groupby_price_graph.csv (for Streamlit charts)")

print("\n" + "="*70)
print("DATA PREPARATION COMPLETE")
print("="*70)
print(f"\nDatasets ready for geospatial merge and visualization:")
print(f"  - {len(district_groupby):,} records")
print(f"  - Property type: Flat")
print(f"  - Sorted by 5-year price increase")


# ============================================================================
# OPTIONAL: EXPLORATORY VISUALIZATIONS (COMMENTED OUT)
# ============================================================================
# Uncomment the sections below for exploratory analysis

# # Scatter plot: Price vs 5-year change
# plt.figure(figsize=(10, 6))
# plt.title("Average Price of Flat vs 5-Year Rolling Average % Change")
# plt.xlabel("Average Price (£)")
# plt.ylabel("5 Year Rolling Average % Change")
# plt.scatter(
#     district_groupby['avg_price'],
#     district_groupby['rolling_avg_median_pct_change_5_year'],
#     alpha=0.6
# )
# plt.show()

# # Scatter plot: Price vs transaction volume (London only)
# test = district_groupby[
#     (district_groupby['is_london?'] != 'Outside London') &
#     (district_groupby['property_type'] == 'F')
# ]
# plt.figure(figsize=(10, 6))
# plt.title("Average Price of Flat vs Number of Transactions (London)")
# plt.xlabel("Average Price (£)")
# plt.ylabel("Number of Transactions")
# plt.xlim(300000, 400000)
# plt.ylim(50, 200)
# plt.scatter(test['avg_price'], test['num_transactions'], alpha=0.6)
# plt.show()
