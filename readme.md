# UK Land Registry Data Analysis with Socio-Economic Data Merge
[Streamlit App For London Flats](https://land-registry-merge-socio-economic.streamlit.app/)

## Project Overview

This project analyses historic UK Land Registry data, sorted by postcode district (e.g., SW11, E3). Our approach enriches this data with 2019 socio-economic information, which originally covers finer geographic areas than postcode districts. To align these datasets, we aggregate the socio-economic data from these smaller areas to their corresponding postcode districts using geospatial merging techniques. This process allows us to integrate detailed socio-economic insights with property transaction data. For example, we can calculate the average price for flats in SW11 in 2023, while also providing a socio-economic profile of the area. By merging these datasets, we offer location-based insights, blending property values with socio-economic contexts to uncover deeper trends and patterns.

![Example Dashboard Output Of London Postcode District Comparisons](/Images/LondonDistrictsComparison.png)

## Getting Started

### Production Workflow (Recommended)

This project uses a **script-based workflow** with automated deployment to AWS EMR:

**Quick Start:**
1. Deploy EMR cluster: `cd terraform && terraform apply`
2. Upload raw data: `./scripts/upload_to_bronze.sh ~/Downloads/land_registry_data.csv`
3. Convert to Parquet: `./scripts/run_on_emr.sh bronze_to_silver.py <cluster-id>`
4. Run aggregations: `./scripts/run_on_emr.sh silver_to_gold.py <cluster-id>`

📖 **[Read the EMR Workflow Guide](docs/EMR_WORKFLOW.md)** for detailed instructions.

### Alternative: Interactive Development with EMR Notebooks

For exploratory analysis, you can also use Jupyter notebooks on EMR:

📖 **[Read the Notebook Quick Start Guide](notebooks/QUICKSTART.md)** for setup instructions.

📊 **[See Visual Comparison](notebooks/VISUAL_GUIDE.md)** of notebooks vs scripts workflow.

## Features

- **Interactive Development**: Jupyter notebooks on EMR for cell-by-cell data exploration and transformation with immediate feedback.
- **Data Processing**: Functions are implemented to clean and prepare the UK Land Registry data for analysis, ensuring quality and consistency.
- **Geospatial Merging**: Utilizes geopandas for merging land registry data with socio-economic data on a postcode district level, enabling spatial analysis of socio-economic impacts on property transactions.
- **PySpark Analytics**: Employs PySpark for efficient processing of large datasets, facilitating tasks such as grouping and aggregation by postcode district.
- **Visualization Dashboard**: A Streamlit-based dashboard presents interactive maps and charts, offering users the ability to explore data through various lenses such as price changes, property types, and socio-economic indicators.

## Data Sources

- **Price Paid HM Land Registry**: Sales prices of properties in England and Wales from 1995. The file is around 5Gb and can be downloaded [here](https://www.gov.uk/government/statistical-data-sets/price-paid-data-downloads) Read more in the LandRegistryDataDoc.md file.
- **Postcode District Polygons**: Polygons in shapely format defining Postcode Areas, Districts and Sectors can be downloaded
[here](https://datashare.ed.ac.uk/handle/10283/2597). From Edinburgh DataShare.
- **England Polygons**: Polygons to match onto the socio econmic xlsx file 
- **English Indices of Deprivation - Socio-economic Data** [Statistics](https://www.gov.uk/government/statistics/english-indices-of-deprivation-2019) on relative deprivation in small areas in England. Gives the statistics in a shapely file. Read more in the SocioEconomicDataDoc.md file.

## Built With
- **AWS EMR Clusters**: A Cloud Big Data platform for processing massive amounts of data which can host big data software technologies such as Apache Spark.
- **EMR Notebooks**: Jupyter notebook environment for interactive development and data exploration on EMR clusters.
- **Terraform**: An Infrastructure as Code (IaC) technology used as a clear and convinient way to create an AWS EMR Cluster.
- **Apache Spark**: An open-source programming interface for big data tasks that manipulates clusters of computers and distributed datasets to process large amounts of data.
- **Geopandas**: A python library similar to pandas but also has "shapely" technology for manipulation of geometric objects and "PyProj" for projection and coordinate transformations.
- **Streamlit**: A python dashboarding technology with interactive filters, buttons, widgets, maps, tables and more.
- **Folium**: A python library for making interactive data visualisations on maps utilising Leaflet.js.

## Project Structure

This project follows the **Medallion Architecture** pattern (Bronze → Silver → Gold) for data processing:

```
src/
├── bronze/          # (empty - raw data ingestion handled by scripts/)
├── silver/          # Data transformation (EMR/PySpark)
│   ├── bronze_to_silver.py
│   └── pyspark_functions.py
├── gold/            # Aggregations (EMR/PySpark)
│   └── silver_to_gold.py
├── local/           # Local processing (Pandas/GeoPandas)
│   ├── preprocessing_qa.py
│   ├── geospatial_merge.py
│   ├── qa_groupby_data.py
│   └── local_utils.py
└── dashboard/       # Visualization
    └── streamlit_dash.py
```

### 📁 Core Python Scripts (`src/`)

#### Bronze Layer (Raw Data)
- **Upload Script**: `scripts/upload_to_bronze.sh`
  - Uploads raw CSV to `s3://landregistryproject/bronze/`
  - Handles large files (5GB+) using AWS CLI multipart upload

#### Silver Layer (Cleaned & Partitioned Data)
- **`bronze_to_silver.py`**: CSV to Parquet conversion (one-time setup)
  - Converts raw 5GB CSV to optimized Snappy-compressed Parquet (.snappy.parquet)
  - Partitions data by year for efficient querying
  - Performs data quality checks during conversion
  - Achieves ~2-3x compression ratio
  - Automatically deletes original CSV after successful verification
  - Outputs: `s3://landregistryproject/silver/land_registry_data.parquet/` (partitioned by year)

- **`pyspark_functions.py`**: Utility functions for PySpark processing
  - Postcode parsing and geographic classification (London detection)
  - Statistical aggregation functions with quality metrics
  - Time-series analysis (rolling averages, percentage changes)
  - Data quality assessment functions

#### Gold Layer (Aggregated Data)
- **`silver_to_gold.py`**: Main aggregation pipeline that processes the full dataset
  - Groups transactions by postcode district, property type, and year
  - Calculates comprehensive price statistics (mean, median, percentiles, skewness, kurtosis)
  - Computes year-over-year price changes and rolling averages
  - Outputs: `s3://landregistryproject/gold/area_pct_change.csv/`, `district_pct_change.csv/`, `sector_pct_change.csv/`

#### Local Processing Scripts (Run on your machine)
- **`local/preprocessing_qa.py`**: Data quality assurance for raw datasets
  - Validates Land Registry data (postcodes, prices, dates)
  - Checks geospatial polygon validity
  - Repairs invalid geometries using buffer(0) method
  - Ensures data integrity before PySpark processing

- **`local/qa_groupby_data.py`**: Prepares Gold layer output for visualization
  - Downloads Gold CSVs from S3
  - Filters low-quality samples (insufficient transaction counts)
  - Calculates 5-year rolling average price changes
  - Sorts by price increase for hotspot identification
  - Exports cleaned datasets for Streamlit dashboard

- **`local/geospatial_merge.py`**: Merges transaction data with socio-economic indicators
  - Downloads Gold layer CSVs from S3
  - Performs spatial joins (LSOA polygons within postcode districts)
  - Aggregates socio-economic data to postcode district level
  - Merges with transaction statistics
  - Outputs: `district_groupby_socio_economic.gpkg` for visualization

- **`local/local_utils.py`**: General utility functions for local processing
  - Data cleaning and preprocessing helpers
  - Postcode validation and formatting
  - Socio-economic column name standardization

#### Dashboard
- **`dashboard/streamlit_dash.py`**: Interactive dashboard for data exploration
  - Interactive maps with property price overlays
  - Time-series charts for price trends
  - Filters for property type, region, and year
  - Socio-economic indicator comparisons

### 📁 Automation & Deployment

- **`.github/workflows/sync-scripts-to-s3.yml`**: GitHub Actions workflow
  - Automatically syncs `src/*.py` files to S3 on push to main
  - Triggered on changes to Python scripts
  - Ensures EMR always runs latest code version

- **`scripts/upload_to_bronze.sh`**: Upload large CSV files to Bronze layer
  - Handles files larger than 5GB (AWS Console UI limit)
  - Uses AWS CLI multipart upload
  - Shows progress during upload
  - Uploads to: `s3://landregistryproject/bronze/`
  - Usage: `./scripts/upload_to_bronze.sh ~/Downloads/land_registry_data.csv`

- **`scripts/run_on_emr.sh`**: Helper script for EMR job submission
  - Automatically detects script location (silver/ or gold/)
  - Uploads script to S3
  - Automatically uploads dependencies (e.g., pyspark_functions.py)
  - Submits EMR step with `--py-files` for dependencies
  - Provides monitoring commands
  - Usage: `./scripts/run_on_emr.sh bronze_to_silver.py <cluster-id>`
  - Usage: `./scripts/run_on_emr.sh silver_to_gold.py <cluster-id>`

### 📁 Documentation

- **`docs/EMR_WORKFLOW.md`**: Complete guide to the EMR workflow
  - Automatic sync setup (GitHub Actions)
  - Manual script execution methods
  - Monitoring and troubleshooting
  - Full pipeline example

- **`notebooks/QUICKSTART.md`**: Quick start guide for EMR Notebooks (alternative workflow)
- **`notebooks/README.md`**: Comprehensive notebook setup guide

### 📁 Infrastructure

- **`terraform/`**: Infrastructure as Code for AWS EMR cluster
  - `main.tf`: EMR cluster configuration with Spark and Hadoop
  - `iam.tf`: IAM roles and policies (service role, EC2 role, auto-scaling)
  - `security_groups.tf`: Network security for master and core nodes
  - `variables.tf`: Configurable parameters (instance types, region, etc.)
  - `outputs.tf`: Cluster ID, connection details, and helpful commands
  - `terraform.tfvars.example`: Example configuration file
  - `README.md`: Comprehensive Terraform documentation

## Workflow

### Development → Deployment → Execution

```
1. (One-time) Upload CSV to S3: ./scripts/upload_csv_to_s3.sh ~/Downloads/land_registry_data.csv
2. (One-time) Convert CSV to Parquet: ./scripts/run_on_emr.sh land_registry_ingestion.py <cluster-id>
3. Edit scripts locally (src/*.py)
4. Push to GitHub (main branch)
5. GitHub Actions syncs to S3 automatically
6. Run on EMR: ./scripts/run_on_emr.sh transaction_groupby.py <cluster-id>
7. Download results from S3
8. Run local post-processing (qa_groupby_data.py, geospatial_merge.py)
9. Launch Streamlit dashboard
```

See **[EMR Workflow Guide](docs/EMR_WORKFLOW.md)** for detailed instructions.

