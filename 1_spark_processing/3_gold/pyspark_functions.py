"""
PySpark Utility Functions for Land Registry Analysis
=====================================================

This module provides reusable PySpark functions for processing and analyzing UK Land
Registry property transaction data. It includes utilities for:

    - UK postcode parsing and geographic classification
    - Statistical aggregations (mean, median, percentiles, variance)
    - Time-series analysis (year-over-year changes, rolling averages)
    - Data quality evaluation

Functions:
    split_postcode: Parse UK postcodes into area, district, and sector
    classify_london_postcode: Classify postcodes as Central/Greater/Outside London
    groupby_calc_price: Calculate comprehensive price statistics for grouped data
    calculate_pct_change: Compute year-over-year percentage changes and rolling averages
    evaluate_sample_quality: Flag statistically reliable samples based on thresholds

Author: Land Registry Analysis Project
"""

# ============================================================================
# IMPORTS
# ============================================================================
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    udf, col, avg, count, expr, year, lag, when,
    stddev, abs, round, skewness, kurtosis
)
from pyspark.sql.types import StringType, StructType, StructField
from pyspark.sql.window import Window
from postcode_utils import classify_london_postcode, split_postcode


# ============================================================================
# POSTCODE PARSING AND CLASSIFICATION
# ============================================================================

# ============================================================================
# STATISTICAL AGGREGATION FUNCTIONS
# ============================================================================

def groupby_calc_price(df, group_cols):
    """
    Calculate comprehensive price statistics for grouped property transaction data.

    This function performs a groupBy aggregation on the provided DataFrame and calculates
    a wide range of statistical measures including central tendency, dispersion, and
    distribution shape metrics.

    Args:
        df (pyspark.sql.DataFrame): Input DataFrame containing property transaction data
                                    with at least a 'price' column
        group_cols (list or str): Column name(s) to group by. Can be a single string or
                                  list of column names (e.g., ['postcode_area', 'year'])

    Returns:
        pyspark.sql.DataFrame: Aggregated DataFrame with the following columns:
            - Original grouping columns
            - num_transactions: Count of transactions in the group
            - avg_price: Mean price
            - stddev_price: Standard deviation of prices
            - 25th/50th/75th/90th/95th_percentile_price: Price percentiles
            - median_price: Median price (same as 50th percentile)
            - skewness_price: Skewness of price distribution
            - kurtosis_price: Kurtosis of price distribution
            - coef_var: Coefficient of variation (stddev/mean * 100)
            - iqr: Interquartile range (75th - 25th percentile)
            - median_mean_diff: Absolute difference between median and mean
            - median_mean_diff_pct: Median-mean difference as % of median
            - iqr_pct: IQR as % of median

    Example:
        >>> area_stats = groupby_calc_price(df, ['postcode_area', 'year'])
        >>> area_stats.show()
    """
    # Ensure group_cols is a list for consistent handling
    if not isinstance(group_cols, list):
        group_cols = [group_cols]

    # Perform groupBy aggregation with comprehensive statistics
    aggregated_df = df.groupBy(*group_cols) \
        .agg(
            count("*").alias("num_transactions"),
            round(avg("price"), 1).alias("avg_price"),
            round(stddev("price"), 1).alias("stddev_price"),
            round(expr("percentile_approx(price, 0.25)"), 1).alias("25th_percentile_price"),
            round(expr("percentile_approx(price, 0.5)"), 1).alias("median_price"),
            round(expr("percentile_approx(price, 0.75)"), 1).alias("75th_percentile_price"),
            round(expr("percentile_approx(price, 0.90)"), 1).alias("90th_percentile_price"),
            round(expr("percentile_approx(price, 0.95)"), 1).alias("95th_percentile_price"),
            round(skewness("price"), 2).alias("skewness_price"),
            round(kurtosis("price"), 2).alias("kurtosis_price")
        )

    # Calculate derived metrics for data quality assessment
    aggregated_df = aggregated_df \
        .withColumn("coef_var",
                    round((col("stddev_price") / col("avg_price")) * 100, 1)) \
        .withColumn("iqr",
                    round((col("75th_percentile_price") - col("25th_percentile_price")), 1)) \
        .withColumn("median_mean_diff",
                    round((col("median_price") - col("avg_price")), 1)) \
        .withColumn("median_mean_diff_pct",
                    round(abs(col("median_mean_diff") / col("median_price")) * 100, 1)) \
        .withColumn("iqr_pct",
                    round(col("iqr") / col("median_price") * 100, 1))

    return aggregated_df


# ============================================================================
# TIME-SERIES ANALYSIS FUNCTIONS
# ============================================================================



def calculate_pct_change(df, partition_cols):
    """
    Calculate year-over-year percentage changes and rolling averages for price data.

    This function computes temporal price change metrics within each partition (e.g.,
    each postcode area). It calculates:
        - Year-over-year percentage change in median price
        - 2-year rolling average of percentage changes
        - 5-year rolling average of percentage changes

    Args:
        df (pyspark.sql.DataFrame): Input DataFrame with 'year' and 'median_price' columns
        partition_cols (list): Columns to partition by (e.g., ['postcode_area', 'property_type'])
                               Note: 'year' will be automatically excluded from partitioning

    Returns:
        pyspark.sql.DataFrame: DataFrame with additional columns:
            - lag_median_price: Previous year's median price
            - median_pct_change_1_year: Year-over-year % change
            - roll_median_pct_2_year: 2-year rolling average % change
            - roll_median_pct_5_year: 5-year rolling average % change

    Example:
        >>> df_with_changes = calculate_pct_change(area_df, ['postcode_area', 'property_type'])
    """
    # Ensure 'year' is not in partition columns (it's used for ordering)
    partition_cols = [col for col in partition_cols if col != 'year']

    # Define window specification: partition by location/type, order by year
    windowSpec = Window.partitionBy(*partition_cols).orderBy("year")

    # Get previous year's median price using lag function
    df = df.withColumn("lag_median_price", lag("median_price", 1).over(windowSpec))

    # Calculate year-over-year percentage change
    df = df.withColumn("median_pct_change_1_year",
                       (col("median_price") - col("lag_median_price")) * 100 / col("lag_median_price"))

    # Define rolling window specifications
    windowSpec2Year = windowSpec.rowsBetween(-1, 0)  # Current + 1 previous year
    windowSpec5Year = windowSpec.rowsBetween(-4, 0)  # Current + 4 previous years

    # Calculate rolling averages of percentage changes
    df = df.withColumn("roll_median_pct_2_year",
                       avg(col("median_pct_change_1_year")).over(windowSpec2Year))
    df = df.withColumn("roll_median_pct_5_year",
                       avg(col("median_pct_change_1_year")).over(windowSpec5Year))

    # Round all percentage values to 1 decimal place
    df = df.withColumn("median_pct_change_1_year",
                       round(col("median_pct_change_1_year"), 1))
    df = df.withColumn("roll_median_pct_2_year",
                       round(col("roll_median_pct_2_year"), 1))
    df = df.withColumn("roll_median_pct_5_year",
                       round(col("roll_median_pct_5_year"), 1))

    # Replace null values (e.g., first year has no previous year) with 0
    df = df.fillna(0)

    return df


# ============================================================================
# DATA QUALITY EVALUATION
# ============================================================================

def evaluate_sample_quality(df, params):
    """
    Flag statistically reliable samples based on quality thresholds.

    This function adds an 'is_good_sample' boolean column that indicates whether
    a grouped sample meets minimum quality standards for statistical reliability.

    Quality criteria:
        - Sufficient sample size (Central Limit Theorem)
        - Low coefficient of variation (consistent prices)
        - Small median-mean difference (symmetric distribution)
        - Reasonable IQR relative to median (not too dispersed)

    Args:
        df (pyspark.sql.DataFrame): DataFrame with statistical columns from groupby_calc_price
        params (dict): Dictionary of quality thresholds with keys:
            - min_transactions: Minimum number of transactions (default: 30)
            - max_coef_var: Maximum coefficient of variation % (default: 50)
            - max_median_mean_diff_pct: Max median-mean diff % (default: 30)
            - max_iqr_pct: Maximum IQR as % of median (default: 25)

    Returns:
        pyspark.sql.DataFrame: Input DataFrame with added 'is_good_sample' boolean column

    Example:
        >>> quality_params = {'min_transactions': 30, 'max_coef_var': 50}
        >>> df_with_quality = evaluate_sample_quality(df, quality_params)
        >>> good_samples = df_with_quality.filter(col("is_good_sample") == True)
    """
    # Extract thresholds from params dictionary with defaults
    min_transactions = params.get("min_transactions", 30)
    max_coef_var = params.get("max_coef_var", 50)
    max_median_mean_diff_pct = params.get("max_median_mean_diff_pct", 30)
    max_iqr_pct = params.get("max_iqr_pct", 25)

    # Create boolean flag based on all quality criteria
    df = df.withColumn("is_good_sample",
                       (col("num_transactions") >= min_transactions) &
                       (col("coef_var") <= max_coef_var) &
                       (col("median_mean_diff_pct") <= max_median_mean_diff_pct) &
                       (col("iqr_pct") <= max_iqr_pct))

    return df
