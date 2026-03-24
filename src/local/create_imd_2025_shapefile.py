"""
Create IMD 2025 Shapefile from CSV and LSOA Boundaries
=======================================================

This script merges the 2025 Indices of Multiple Deprivation (IMD) CSV data
with LSOA (Lower Layer Super Output Area) boundary shapefiles to create
a geospatial dataset equivalent to IMD_2019.shp but for 2025.

Process:
    1. Load LSOA 2011 boundary shapefiles (polygons)
    2. Load IMD 2025 CSV data (statistics)
    3. Merge on LSOA code
    4. Export as shapefile for use in geospatial_merge.py

Input Files (UPDATE THESE PATHS):
    - LSOA Boundaries: Path to LSOA shapefile directory
    - IMD 2025 CSV: Path to the 2025 deprivation statistics CSV

Output:
    - English_IMD_2025/IMD_2025.shp: Merged geospatial dataset

Author: Land Registry Analysis Project
Date: 2026-03-24
"""

#%% ============================================================================
# IMPORTS
# ============================================================================
import geopandas as gpd
import pandas as pd
import os
import sys

# Ensure openpyxl is available for reading Excel files
try:
    import openpyxl
except ImportError:
    print("WARNING: openpyxl not installed. Installing now...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl"])
    import openpyxl

print("="*70)
print("CREATE IMD 2025 SHAPEFILE FROM CSV + LSOA BOUNDARIES")
print("="*70)


#%% ============================================================================
# CONFIGURATION - UPDATE THESE PATHS
# ============================================================================
print("\n--- Configuration ---")

# Updated paths to match your uploaded files
LSOA_SHAPEFILE_PATH = "Lower_layer_Super_Output_Areas_Dec_2011/LSOA_2011_EW_BFC_V3.shp"
IMD_2025_EXCEL_PATH = "Indices-of-Deprivation-2025.xlsx"
OUTPUT_DIR = "."  # Current directory (src/local)
OUTPUT_SHAPEFILE = "IMD_2025.shp"

print(f"LSOA Shapefile: {LSOA_SHAPEFILE_PATH}")
print(f"IMD 2025 Excel: {IMD_2025_EXCEL_PATH}")
print(f"Output Directory: {OUTPUT_DIR} (current directory)")


#%% ============================================================================
# SECTION 1: LOAD LSOA BOUNDARY SHAPEFILES
# ============================================================================
print("\n--- Loading LSOA Boundary Shapefiles ---")

if not os.path.exists(LSOA_SHAPEFILE_PATH):
    print(f"ERROR: LSOA shapefile not found at: {LSOA_SHAPEFILE_PATH}")
    print("\nPlease download LSOA boundaries from:")
    print("https://geoportal.statistics.gov.uk/datasets/ons::lower-layer-super-output-areas-december-2011-boundaries-ew-bfc-v3/about")
    print("\nExtract the ZIP and update LSOA_SHAPEFILE_PATH in this script.")
    sys.exit(1)

lsoa_boundaries = gpd.read_file(LSOA_SHAPEFILE_PATH)
print(f"Loaded {len(lsoa_boundaries):,} LSOA boundary polygons")
print(f"CRS: {lsoa_boundaries.crs}")
print(f"Columns: {list(lsoa_boundaries.columns)}")

# Identify the LSOA code column (usually 'LSOA11CD' or similar)
lsoa_code_col = None
for col in lsoa_boundaries.columns:
    if 'LSOA' in col.upper() and 'CD' in col.upper():
        lsoa_code_col = col
        break

if lsoa_code_col is None:
    print("\nERROR: Could not find LSOA code column in shapefile.")
    print("Available columns:", list(lsoa_boundaries.columns))
    print("Please manually set lsoa_code_col variable.")
    sys.exit(1)

print(f"Using LSOA code column: '{lsoa_code_col}'")
print(f"Sample LSOA codes: {lsoa_boundaries[lsoa_code_col].head(3).tolist()}")


#%% ============================================================================
# SECTION 2: LOAD IMD 2025 EXCEL DATA
# ============================================================================
print("\n--- Loading IMD 2025 Excel Data ---")

if not os.path.exists(IMD_2025_EXCEL_PATH):
    print(f"ERROR: IMD 2025 Excel file not found at: {IMD_2025_EXCEL_PATH}")
    print("\nPlease download IMD 2025 data from:")
    print("https://www.gov.uk/government/statistics/english-indices-of-deprivation-2025")
    print("\nUpdate IMD_2025_EXCEL_PATH in this script.")
    sys.exit(1)

# Read Excel file - may have multiple sheets, we'll try to detect the right one
excel_file = pd.ExcelFile(IMD_2025_EXCEL_PATH)
print(f"Excel file contains {len(excel_file.sheet_names)} sheet(s): {excel_file.sheet_names}")

# Try to find the main data sheet (usually first sheet or one with 'IMD' in name)
data_sheet = None
for sheet in excel_file.sheet_names:
    if 'IOD' in sheet.upper() or 'IMD' in sheet.upper() or 'INDEX' in sheet.upper() or 'DATA' in sheet.upper() or 'SUB' in sheet.upper():
        data_sheet = sheet
        break

if data_sheet is None:
    # Skip 'Notes' sheet if it exists
    for sheet in excel_file.sheet_names:
        if 'NOTES' not in sheet.upper():
            data_sheet = sheet
            break

    if data_sheet is None:
        data_sheet = excel_file.sheet_names[0]  # Last resort: use first sheet
    print(f"Using sheet: '{data_sheet}'")
else:
    print(f"Using sheet: '{data_sheet}'")

imd_2025 = pd.read_excel(IMD_2025_EXCEL_PATH, sheet_name=data_sheet)
print(f"Loaded {len(imd_2025):,} rows of IMD 2025 data")
print(f"Columns ({len(imd_2025.columns)}): {list(imd_2025.columns[:10])}...")  # Show first 10 columns

# Identify the LSOA code column in the CSV
imd_lsoa_col = None
for col in imd_2025.columns:
    if 'LSOA' in col.upper() and 'CODE' in col.upper():
        imd_lsoa_col = col
        break
    elif 'LSOA' in col.upper() and 'CD' in col.upper():
        imd_lsoa_col = col
        break

if imd_lsoa_col is None:
    # Try first column if it looks like an LSOA code
    first_col_sample = str(imd_2025.iloc[0, 0])
    if first_col_sample.startswith('E') and len(first_col_sample) == 9:
        imd_lsoa_col = imd_2025.columns[0]
        print(f"WARNING: Guessing LSOA column is '{imd_lsoa_col}' based on first row")
    else:
        print("\nERROR: Could not find LSOA code column in CSV.")
        print("Available columns:", list(imd_2025.columns))
        print("Please manually set imd_lsoa_col variable.")
        sys.exit(1)

print(f"Using LSOA code column: '{imd_lsoa_col}'")
print(f"Sample LSOA codes: {imd_2025[imd_lsoa_col].head(3).tolist()}")


#%% ============================================================================
# SECTION 3: MERGE BOUNDARIES WITH IMD DATA
# ============================================================================
print("\n--- Merging LSOA Boundaries with IMD 2025 Data ---")
print(f"Merging on: {lsoa_code_col} (shapefile) = {imd_lsoa_col} (CSV)")

# Perform the merge
imd_2025_gdf = lsoa_boundaries.merge(
    imd_2025,
    left_on=lsoa_code_col,
    right_on=imd_lsoa_col,
    how='inner'  # Only keep LSOAs that have IMD data
)

print(f"Merged dataset contains {len(imd_2025_gdf):,} LSOAs")
print(f"Columns in merged dataset: {len(imd_2025_gdf.columns)}")

# Check for unmatched records
unmatched_boundaries = len(lsoa_boundaries) - len(imd_2025_gdf)
unmatched_imd = len(imd_2025) - len(imd_2025_gdf)

if unmatched_boundaries > 0:
    print(f"WARNING: {unmatched_boundaries} LSOA boundaries had no IMD data")
if unmatched_imd > 0:
    print(f"WARNING: {unmatched_imd} IMD records had no matching boundary")


#%% ============================================================================
# SECTION 4: EXPORT AS SHAPEFILE
# ============================================================================
print("\n--- Exporting IMD 2025 Shapefile ---")

# Create output directory if it doesn't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)

output_path = os.path.join(OUTPUT_DIR, OUTPUT_SHAPEFILE)
imd_2025_gdf.to_file(output_path)

print(f"✓ Saved: {output_path}")
print(f"  - {len(imd_2025_gdf):,} LSOA polygons")
print(f"  - {len(imd_2025_gdf.columns)} columns")
print(f"  - CRS: {imd_2025_gdf.crs}")

print("\n" + "="*70)
print("IMD 2025 SHAPEFILE CREATION COMPLETE")
print("="*70)
print(f"\nYou can now use this file in geospatial_merge.py by updating:")
print(f"  Line 72: socio_economic = gpd.read_file('src/local/{OUTPUT_SHAPEFILE}')")

