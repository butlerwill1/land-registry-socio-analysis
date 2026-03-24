"""
Land Registry Data Ingestion - CSV to Parquet Conversion
=========================================================

This script converts the raw 5GB Land Registry CSV file into optimized 
Snappy-compressed Parquet format, partitioned by year for efficient querying.

Process Overview:
    1. Configure Spark session with optimized settings
    2. Define explicit schema for Land Registry data
    3. Read CSV from S3 with schema validation
    4. Perform data quality checks (nulls, distributions, ranges)
    5. Add year column for partitioning
    6. Write as partitioned Parquet with Snappy compression (.snappy.parquet)
    7. Verify conversion and test partition pruning
    8. Delete original CSV file to save storage costs (after verification)

Input:
    - s3://landregistryproject/bronze/land_registry_data.csv (~5GB)

Output:
    - s3://landregistryproject/silver/land_registry_data.parquet/ (~1.5-2GB)
    - Partitioned by year for efficient time-based queries

Performance:
    - Expected compression ratio: 2-3x
    - Partition pruning enables fast year-specific queries
    - Snappy compression balances speed and compression

Usage:
    # Run on EMR cluster
    ./scripts/run_on_emr.sh land_registry_ingestion.py <cluster-id>
    
    # Or submit directly
    aws emr add-steps --cluster-id j-XXXXX \\
        --steps Type=Spark,Name="Land Registry Ingestion",\\
        Args=[--deploy-mode,cluster,--master,yarn,\\
        s3://landregistryproject/scripts/land_registry_ingestion.py]

Author: Land Registry Analysis Project
"""

# ============================================================================
# IMPORTS
# ============================================================================
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DateType
from pyspark.sql.functions import col, year, count, when, sum as spark_sum
import time


# ============================================================================
# SPARK SESSION CONFIGURATION
# ============================================================================
def create_spark_session():
    """
    Create and configure Spark session with optimized settings for Parquet conversion.
    
    Returns:
        SparkSession: Configured Spark session
    """
    print("=" * 70)
    print("LAND REGISTRY DATA INGESTION: CSV → PARQUET")
    print("=" * 70)
    
    spark = SparkSession.builder \
        .appName("Land Registry CSV to Parquet Conversion") \
        .config("spark.sql.parquet.compression.codec", "snappy") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .config("spark.hadoop.fs.s3a.fast.upload", "true") \
        .getOrCreate()
    
    print(f"\n✓ Spark session created")
    print(f"  Spark version: {spark.version}")
    print(f"  Compression codec: snappy")
    print(f"  Adaptive query execution: enabled")
    
    return spark


# ============================================================================
# SCHEMA DEFINITION
# ============================================================================
def get_land_registry_schema():
    """
    Define explicit schema for Land Registry Price Paid Data.
    
    Based on: https://www.gov.uk/government/statistical-data-sets/price-paid-data-downloads
    
    Returns:
        StructType: Schema for Land Registry data
    """
    schema = StructType([
        StructField("transaction_id", StringType(), True),
        StructField("price", IntegerType(), True),
        StructField("date_transfer", DateType(), True),
        StructField("postcode", StringType(), True),
        StructField("property_type", StringType(), True),
        StructField("old_new", StringType(), True),
        StructField("duration", StringType(), True),
        StructField("paon", StringType(), True),
        StructField("saon", StringType(), True),
        StructField("street", StringType(), True),
        StructField("locality", StringType(), True),
        StructField("town/city", StringType(), True),
        StructField("district", StringType(), True),
        StructField("county", StringType(), True),
        StructField("ppd_category", StringType(), True),
        StructField("record_status", StringType(), True)
    ])
    
    print(f"\n✓ Schema defined with {len(schema.fields)} fields")
    return schema


# ============================================================================
# DATA LOADING
# ============================================================================
def load_csv_data(spark, csv_path, schema):
    """
    Load Land Registry CSV data from S3 with schema validation.
    
    Args:
        spark (SparkSession): Active Spark session
        csv_path (str): S3 path to CSV file
        schema (StructType): Data schema
    
    Returns:
        DataFrame: Loaded data
    """
    print(f"\n--- Loading CSV Data ---")
    print(f"  Source: {csv_path}")
    
    start_time = time.time()
    
    df = spark.read.csv(
        csv_path,
        header=False,  # Land Registry data has no header
        schema=schema,
        mode="DROPMALFORMED"  # Skip malformed rows
    )
    
    row_count = df.count()
    elapsed = time.time() - start_time
    
    print(f"  ✓ Loaded {row_count:,} rows in {elapsed:.1f} seconds")

    return df


# ============================================================================
# DATA QUALITY CHECKS
# ============================================================================
def perform_quality_checks(df):
    """
    Perform comprehensive data quality checks on loaded data.

    Args:
        df (DataFrame): Loaded Land Registry data
    """
    print(f"\n--- Data Quality Checks ---")

    # Check 1: Null values in critical columns
    print("\n  1. Checking for null values in critical columns...")
    critical_cols = ['price', 'date_transfer', 'postcode', 'property_type']

    null_counts = df.select([
        spark_sum(when(col(c).isNull(), 1).otherwise(0)).alias(c)
        for c in critical_cols
    ]).collect()[0]

    for col_name in critical_cols:
        null_count = null_counts[col_name]
        print(f"     {col_name}: {null_count:,} nulls")

    # Check 2: Price distribution
    print("\n  2. Price distribution:")
    price_stats = df.select('price').describe().collect()
    for row in price_stats:
        print(f"     {row['summary']}: £{float(row['price']):,.0f}")

    # Check 3: Property types
    print("\n  3. Property type distribution:")
    prop_types = df.groupBy('property_type').count().orderBy('count', ascending=False).collect()
    for row in prop_types[:10]:  # Top 10
        print(f"     {row['property_type']}: {row['count']:,} transactions")

    # Check 4: Date range
    print("\n  4. Date range:")
    date_range = df.select(col('date_transfer')).agg(
        {'date_transfer': 'min', 'date_transfer': 'max'}
    ).collect()[0]
    print(f"     Earliest: {date_range['min(date_transfer)']}")
    print(f"     Latest: {date_range['max(date_transfer)']}")

    print("\n  ✓ Quality checks complete")


# ============================================================================
# DATA TRANSFORMATION
# ============================================================================
def add_partitioning_column(df):
    """
    Add year column for partitioning.

    Args:
        df (DataFrame): Input data

    Returns:
        DataFrame: Data with year column
    """
    print(f"\n--- Adding Partitioning Column ---")

    df = df.withColumn("year", year(col("date_transfer")))

    # Show year distribution
    print("\n  Year distribution:")
    year_dist = df.groupBy('year').count().orderBy('year').collect()

    # Show first 10 and last 10 years
    for row in year_dist[:10]:
        print(f"     {row['year']}: {row['count']:,} transactions")

    if len(year_dist) > 20:
        print("     ...")
        for row in year_dist[-10:]:
            print(f"     {row['year']}: {row['count']:,} transactions")

    print(f"\n  ✓ Added year column ({len(year_dist)} unique years)")

    return df


# ============================================================================
# PARQUET CONVERSION
# ============================================================================
def write_parquet(df, output_path):
    """
    Write DataFrame as partitioned Parquet with Snappy compression.

    Args:
        df (DataFrame): Data to write
        output_path (str): S3 output path
    """
    print(f"\n--- Writing Parquet Files ---")
    print(f"  Output: {output_path}")
    print(f"  Partitioning: by year")
    print(f"  Compression: snappy")
    print(f"  Format: .snappy.parquet")

    start_time = time.time()

    df.write \
        .mode("overwrite") \
        .partitionBy("year") \
        .option("compression", "snappy") \
        .parquet(output_path)

    elapsed = time.time() - start_time

    print(f"\n  ✓ Parquet files written in {elapsed:.1f} seconds")
    print(f"  ✓ Files saved with .snappy.parquet extension")


# ============================================================================
# VERIFICATION
# ============================================================================
def verify_conversion(spark, parquet_path, original_count):
    """
    Verify Parquet conversion by reading back and comparing counts.

    Args:
        spark (SparkSession): Active Spark session
        parquet_path (str): Path to Parquet files
        original_count (int): Original row count
    """
    print(f"\n--- Verifying Conversion ---")

    # Read back Parquet
    df_parquet = spark.read.parquet(parquet_path)
    parquet_count = df_parquet.count()

    print(f"  Original row count: {original_count:,}")
    print(f"  Parquet row count:  {parquet_count:,}")
    print(f"  Match: {parquet_count == original_count}")

    if parquet_count != original_count:
        print(f"  ⚠ WARNING: Row count mismatch!")
        return False

    # Test partition pruning
    print(f"\n  Testing partition pruning (year=2023)...")
    df_2023 = df_parquet.filter(col('year') == 2023)
    count_2023 = df_2023.count()
    print(f"  2023 transactions: {count_2023:,}")

    # Show sample
    print(f"\n  Sample data:")
    df_parquet.show(5, truncate=False)

    print(f"\n  ✓ Verification complete")
    return True


# ============================================================================
# CLEANUP
# ============================================================================
def delete_original_csv(spark, csv_path):
    """
    Delete the original CSV file from S3 after successful conversion.

    Args:
        spark (SparkSession): Active Spark session
        csv_path (str): S3 path to CSV file to delete

    Returns:
        bool: True if deletion successful, False otherwise
    """
    print(f"\n--- Cleaning Up Original CSV ---")
    print(f"  Deleting: {csv_path}")

    try:
        # Use Hadoop FileSystem API to delete the file
        from pyspark import SparkContext

        # Get Hadoop configuration
        sc = spark.sparkContext
        hadoop_conf = sc._jsc.hadoopConfiguration()

        # Get FileSystem
        fs_class = sc._jvm.org.apache.hadoop.fs.FileSystem
        path_class = sc._jvm.org.apache.hadoop.fs.Path

        # Create path object
        path = path_class(csv_path)

        # Get filesystem
        fs = fs_class.get(path.toUri(), hadoop_conf)

        # Delete the file
        deleted = fs.delete(path, False)  # False = don't delete recursively

        if deleted:
            print(f"  ✓ Original CSV file deleted successfully")
            print(f"  ✓ Storage space freed")
            return True
        else:
            print(f"  ⚠ WARNING: Could not delete CSV file (may not exist)")
            return False

    except Exception as e:
        print(f"  ⚠ WARNING: Error deleting CSV file: {str(e)}")
        print(f"  You can manually delete it with:")
        print(f"    aws s3 rm {csv_path}")
        return False


# ============================================================================
# MAIN EXECUTION
# ============================================================================
def main():
    """
    Main execution function for Land Registry CSV to Parquet conversion.
    """
    # Configuration
    CSV_PATH = "s3a://landregistryproject/bronze/land_registry_data.csv"
    PARQUET_PATH = "s3a://landregistryproject/silver/land_registry_data.parquet"
    DELETE_ORIGINAL = True  # Set to False to keep the original CSV

    try:
        # Step 1: Create Spark session
        spark = create_spark_session()

        # Step 2: Define schema
        schema = get_land_registry_schema()

        # Step 3: Load CSV data
        df = load_csv_data(spark, CSV_PATH, schema)
        original_count = df.count()

        # Step 4: Perform quality checks
        perform_quality_checks(df)

        # Step 5: Add partitioning column
        df = add_partitioning_column(df)

        # Step 6: Write Parquet
        write_parquet(df, PARQUET_PATH)

        # Step 7: Verify conversion
        success = verify_conversion(spark, PARQUET_PATH, original_count)

        if not success:
            print("\n⚠ Verification failed - NOT deleting original CSV")
            spark.stop()
            return 1

        # Step 8: Delete original CSV (if enabled and verification passed)
        if DELETE_ORIGINAL:
            delete_original_csv(spark, CSV_PATH)
        else:
            print(f"\n⚠ Original CSV retained at: {CSV_PATH}")
            print(f"  To delete manually, run:")
            print(f"    aws s3 rm {CSV_PATH}")

        # Summary
        print("\n" + "=" * 70)
        print("CONVERSION COMPLETE")
        print("=" * 70)
        print(f"\n✓ CSV successfully converted to Snappy Parquet")
        print(f"✓ Data partitioned by year for efficient querying")
        print(f"✓ Files saved with .snappy.parquet extension")
        print(f"✓ Expected compression: ~2-3x (5GB → ~1.5-2GB)")
        if DELETE_ORIGINAL:
            print(f"✓ Original CSV file deleted to save storage costs")
        print(f"\nOutput location: {PARQUET_PATH}")
        print(f"\nNext steps:")
        print(f"  1. Check file sizes:")
        print(f"     aws s3 ls --summarize --human-readable --recursive s3://landregistryproject/land_registry_data.parquet/")
        print(f"  2. Use Parquet file in transaction_groupby.py")
        print(f"  3. Query specific years using partition pruning")

        # Stop Spark session
        spark.stop()

        return 0

    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())

