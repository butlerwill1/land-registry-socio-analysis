# EMR Workflow Guide

## Overview

This project uses AWS EMR (Elastic MapReduce) with Apache Spark to process large-scale UK Land Registry data. Python scripts are automatically synced to S3 and can be executed on EMR clusters.

## Quick Start Checklist

Before running any scripts on EMR, use the preflight check:

```bash
# Run preflight check (without cluster)
./scripts/preflight_check.sh

# Or check with a specific cluster ID
./scripts/preflight_check.sh j-XXXXXXXXXXXXX
```

The preflight check verifies:
- ✓ AWS CLI is installed and configured
- ✓ S3 bucket exists and CSV file is uploaded
- ✓ Terraform configuration is correct (IAM roles, region)
- ✓ EMR cluster is ready (if cluster ID provided)

## Architecture

```
Local Development → GitHub Push → GitHub Actions → S3 → EMR Cluster
```

### Project Structure (Medallion Architecture)

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

### Data Flow

1. **Bronze Layer**: Raw CSV data uploaded to `s3://landregistryproject/bronze/`
2. **Silver Layer**: Cleaned, partitioned Parquet at `s3://landregistryproject/silver/`
3. **Gold Layer**: Aggregated CSVs at `s3://landregistryproject/gold/`
4. **Local Processing**: Enrichment with geospatial/socioeconomic data
5. **Dashboard**: Streamlit visualization

### Deployment Flow

1. **Local Development**: Edit Python scripts in `src/`
2. **GitHub Actions**: Automatically syncs scripts to S3 on push
3. **S3 Storage**: Scripts stored at `s3://landregistryproject/scripts/`
4. **EMR Execution**: Submit scripts as Spark steps to EMR cluster

## Automatic Sync (GitHub Actions)

### Setup

1. Add AWS credentials to GitHub Secrets:
   - Go to repository Settings → Secrets and variables → Actions
   - Add `AWS_ACCESS_KEY_ID`
   - Add `AWS_SECRET_ACCESS_KEY`

2. The workflow (`.github/workflows/sync-scripts-to-s3.yml`) automatically runs when:
   - You push changes to `src/**/*.py` files on the `main` branch
   - You manually trigger it from the Actions tab

### What Gets Synced

- All `.py` files in the `src/` directory
- Synced to: `s3://landregistryproject/scripts/`
- Old files are deleted (using `--delete` flag)

## Manual Script Execution

### Option 1: Using the Helper Script (Recommended)

```bash
# Make the script executable (first time only)
chmod +x scripts/run_on_emr.sh

# Run a script on EMR
./scripts/run_on_emr.sh bronze_to_silver.py j-XXXXXXXXXXXXX
./scripts/run_on_emr.sh silver_to_gold.py j-XXXXXXXXXXXXX
```

The helper script:
- ✅ Automatically detects script location (silver/ or gold/)
- ✅ Uploads the script to S3
- ✅ Automatically uploads dependencies (e.g., `pyspark_functions.py`)
- ✅ Submits the EMR step with `--py-files` for dependencies
- ✅ Provides monitoring commands
- ✅ Optionally waits for completion

### Option 2: Manual AWS CLI Commands

```bash
# 1. Upload script to S3
aws s3 cp src/gold/silver_to_gold.py s3://landregistryproject/scripts/

# 2. Upload dependencies
aws s3 cp src/silver/pyspark_functions.py s3://landregistryproject/scripts/

# 3. Submit EMR step with dependencies
aws emr add-steps \
  --cluster-id j-XXXXXXXXXXXXX \
  --steps Type=Spark,Name="Silver to Gold",ActionOnFailure=CONTINUE,\
Args=[--deploy-mode,client,--master,yarn,--py-files,s3://landregistryproject/scripts/pyspark_functions.py,s3://landregistryproject/scripts/silver_to_gold.py]

# 4. Monitor step status
aws emr describe-step --cluster-id j-XXXXXXXXXXXXX --step-id s-XXXXXXXXXXXXX
```

## Available Scripts

### PySpark Scripts (Run on EMR)

| Script | Location | Description | Dependencies |
|--------|----------|-------------|--------------|
| `bronze_to_silver.py` | `src/silver/` | Convert Bronze CSV to Silver Parquet (one-time) | None |
| `silver_to_gold.py` | `src/gold/` | Aggregate Silver to Gold CSVs | `pyspark_functions.py` |
| `pyspark_functions.py` | `src/silver/` | PySpark utility functions | None |

### Local Scripts (Run on your machine)

| Script | Location | Description | Use Case |
|--------|----------|-------------|----------|
| `preprocessing_qa.py` | `src/local/` | Data quality checks | QA on sample data |
| `geospatial_merge.py` | `src/local/` | Merge with socio-economic data | After PySpark processing |
| `qa_groupby_data.py` | `src/local/` | Prepare data for visualization | After PySpark processing |
| `local_utils.py` | `src/local/` | Pandas/GeoPandas utilities | Used by local scripts |

### Dashboard

| Script | Location | Description |
|--------|----------|-------------|
| `streamlit_dash.py` | `src/dashboard/` | Interactive visualization dashboard |

## Workflow Example

### Full Pipeline

```bash
# 1. Create EMR cluster (if not exists)
cd terraform && terraform apply && cd ..

# 2. Get cluster ID
CLUSTER_ID=$(cd terraform && terraform output -raw emr_cluster_id && cd ..)

# 3. (One-time) Upload raw CSV to Bronze layer
./scripts/upload_to_bronze.sh ~/Downloads/land_registry_data.csv

# 4. (One-time) Convert Bronze CSV to Silver Parquet
./scripts/run_on_emr.sh bronze_to_silver.py $CLUSTER_ID

# 5. Run Silver to Gold aggregation
./scripts/run_on_emr.sh silver_to_gold.py $CLUSTER_ID

# 6. Wait for completion, then download Gold layer results
aws s3 cp s3://landregistryproject/gold/area_pct_change.csv/ ./data/area/ --recursive
aws s3 cp s3://landregistryproject/gold/district_pct_change.csv/ ./data/district/ --recursive
aws s3 cp s3://landregistryproject/gold/sector_pct_change.csv/ ./data/sector/ --recursive

# 7. Run local post-processing
python src/local/qa_groupby_data.py
python src/local/geospatial_merge.py

# 8. Launch Streamlit dashboard
streamlit run src/dashboard/streamlit_dash.py
```

### First-Time Setup (CSV to Parquet)

If you have the raw CSV file and need to convert it to Parquet:

#### Step 1: Upload CSV to S3 (Bronze Layer)

The AWS Console UI has a 5GB upload limit, so use the upload script for large files.
This uploads to the **bronze** layer (raw data):

```bash
# Upload from default location (~/Downloads/land_registry_data.csv)
./scripts/upload_to_bronze.sh

# OR upload from custom location
./scripts/upload_to_bronze.sh ~/Downloads/pp-complete.csv
./scripts/upload_to_bronze.sh /path/to/your/file.csv
```

The file will be uploaded to: `s3://landregistryproject/bronze/land_registry_data.csv`

The script uses **AWS CLI** which:
- Automatically uses multipart upload for files > 8MB
- Handles files up to 5TB (not just 5GB)
- Shows progress during upload
- Automatically retries on failure
- No additional Python packages required

#### Step 2: Convert to Parquet (Silver Layer)

```bash
# Run Bronze → Silver conversion script on EMR
# This will automatically:
#   - Read from bronze layer (raw CSV)
#   - Convert CSV to Snappy Parquet (.snappy.parquet files)
#   - Write to silver layer (processed Parquet)
#   - Partition by year
#   - Verify the conversion
#   - Delete the bronze CSV to save storage costs
./scripts/run_on_emr.sh bronze_to_silver.py $CLUSTER_ID

# Verify conversion (silver layer)
aws s3 ls --summarize --human-readable --recursive s3://landregistryproject/silver/land_registry_data.parquet/

# Check that bronze CSV was deleted
aws s3 ls s3://landregistryproject/bronze/
```

**Data Flow:**
- **Bronze**: `s3://landregistryproject/bronze/` - Raw CSV data from source
- **Silver**: `s3://landregistryproject/silver/` - Cleaned, partitioned Parquet files

**Note:** The conversion script automatically deletes the bronze CSV after successful verification. To keep the original CSV, edit `src/land_registry_ingestion.py` and set `DELETE_ORIGINAL = False`.

## Monitoring

### Check Step Status

```bash
aws emr describe-step \
  --cluster-id j-XXXXXXXXXXXXX \
  --step-id s-XXXXXXXXXXXXX \
  --query 'Step.Status'
```

### View Logs

Logs are available in the AWS Console:
```
https://console.aws.amazon.com/emr/home?region=eu-west-2#/clusterDetails/j-XXXXXXXXXXXXX
```

Or download from S3:
```bash
aws s3 ls s3://aws-logs-ACCOUNT-eu-west-2/elasticmapreduce/j-XXXXXXXXXXXXX/
```

## Troubleshooting

### Script Not Found in S3

```bash
# Verify upload
aws s3 ls s3://landregistryproject/scripts/

# Manually sync if needed
aws s3 sync src/ s3://landregistryproject/scripts/ --exclude "*" --include "*.py"
```

### Import Errors

If you see `ModuleNotFoundError: No module named 'pyspark_functions'`:

```bash
# Ensure dependencies are uploaded
aws s3 cp src/pyspark_functions.py s3://landregistryproject/scripts/

# Or use the helper script which handles this automatically
./scripts/run_on_emr.sh transaction_groupby.py j-XXXXXXXXXXXXX
```

### Step Fails Immediately

Check that:
- ✅ Cluster is in `WAITING` state
- ✅ Script path in S3 is correct
- ✅ Script has no syntax errors (test locally first)

## Cost Optimization

- **Terminate cluster when not in use**: `terraform destroy`
- **Use spot instances**: Already configured in `emr_cluster.tf`
- **Monitor S3 storage**: Old output files accumulate costs

## Next Steps

- See `notebooks/QUICKSTART.md` for interactive Jupyter notebook workflow
- See `README.md` for project overview

