#!/bin/bash

################################################################################
# Upload Land Registry CSV to S3
################################################################################
# This script uploads the Land Registry CSV file to S3 using AWS CLI.
# AWS CLI automatically handles multipart upload for large files (>5GB).
#
# Usage:
#   ./scripts/upload_csv_to_s3.sh
#   ./scripts/upload_csv_to_s3.sh /path/to/your/file.csv
#   ./scripts/upload_csv_to_s3.sh ~/Downloads/pp-complete.csv
#
# The AWS CLI will:
#   - Automatically use multipart upload for files > 8MB
#   - Show progress during upload
#   - Handle files up to 5TB
#   - Retry on failure
#
################################################################################

set -e  # Exit on error

# Configuration
S3_BUCKET="landregistryproject"
S3_KEY="bronze/land_registry_data.csv"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    print_error "AWS CLI is not installed"
    echo ""
    echo "Install it with:"
    echo "  macOS:   brew install awscli"
    echo "  Linux:   sudo apt-get install awscli"
    echo "  Or see:  https://aws.amazon.com/cli/"
    exit 1
fi

# Check if AWS credentials are configured
if ! aws sts get-caller-identity &> /dev/null; then
    print_error "AWS credentials not configured"
    echo ""
    echo "Configure AWS credentials with:"
    echo "  aws configure"
    exit 1
fi

# Default file path
FILE_PATH="${1:-$HOME/Downloads/land_registry_data.csv}"

# Expand ~ to home directory
FILE_PATH="${FILE_PATH/#\~/$HOME}"

# Check if file exists
if [ ! -f "$FILE_PATH" ]; then
    print_error "File not found: $FILE_PATH"
    echo ""
    echo "Usage:"
    echo "  $0 [path/to/file.csv]"
    echo ""
    echo "Examples:"
    echo "  $0"
    echo "  $0 ~/Downloads/land_registry_data.csv"
    exit 1
fi

# Get file size (actual file size, not disk usage)
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    FILE_SIZE=$(ls -lh "$FILE_PATH" | awk '{print $5}')
else
    # Linux
    FILE_SIZE=$(ls -lh "$FILE_PATH" | awk '{print $5}')
fi

# Print summary
echo "======================================================================"
echo "UPLOADING FILE TO S3"
echo "======================================================================"
echo ""
echo "Local file:  $FILE_PATH"
echo "File size:   $FILE_SIZE"
echo "S3 bucket:   $S3_BUCKET"
echo "S3 key:      $S3_KEY"
echo "Full S3 URL: s3://$S3_BUCKET/$S3_KEY"
echo ""

# Confirm upload
read -p "Continue with upload? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_warning "Upload cancelled"
    exit 0
fi

# Upload file
print_info "Starting upload..."
echo ""

# AWS CLI automatically uses multipart upload for files > 8MB
# Note: Using no progress flag for compatibility, or use --no-progress to suppress output
aws s3 cp "$FILE_PATH" "s3://$S3_BUCKET/$S3_KEY"

# Verify upload
if [ $? -eq 0 ]; then
    echo ""
    echo "======================================================================"
    echo "VERIFYING UPLOAD"
    echo "======================================================================"
    echo ""

    # Get local file size
    print_info "Getting local file size..."
    LOCAL_SIZE=$(ls -l "$FILE_PATH" | awk '{print $5}')
    LOCAL_SIZE_GB=$(echo "scale=2; $LOCAL_SIZE / 1024 / 1024 / 1024" | bc)
    echo "  Local file: $LOCAL_SIZE bytes ($LOCAL_SIZE_GB GB)"

    # Get S3 file size
    print_info "Getting S3 file size..."
    S3_SIZE=$(aws s3api head-object --bucket "$S3_BUCKET" --key "$S3_KEY" --query 'ContentLength' --output text)
    S3_SIZE_GB=$(echo "scale=2; $S3_SIZE / 1024 / 1024 / 1024" | bc)
    echo "  S3 file:    $S3_SIZE bytes ($S3_SIZE_GB GB)"
    echo ""

    # Compare sizes
    if [ "$LOCAL_SIZE" -eq "$S3_SIZE" ]; then
        print_info "✓ File sizes match exactly - upload verified!"
        echo ""

        # Get row count
        print_info "Counting rows in local file..."
        LOCAL_ROWS=$(wc -l < "$FILE_PATH" | tr -d ' ')
        echo "  Total rows: $(printf "%'d" $LOCAL_ROWS)"
        echo ""

        echo "======================================================================"
        echo "UPLOAD COMPLETE & VERIFIED"
        echo "======================================================================"
        echo ""
        echo "✓ File successfully uploaded to S3"
        echo "✓ File size verified: $S3_SIZE bytes ($S3_SIZE_GB GB)"
        echo "✓ Expected rows: $(printf "%'d" $LOCAL_ROWS)"
        echo ""
        echo "S3 Location: s3://$S3_BUCKET/$S3_KEY"
        echo ""
        echo "Next steps:"
        echo "  1. Get your EMR cluster ID:"
        echo "     terraform output -raw emr_cluster_id"
        echo ""
        echo "  2. Run the conversion script (will verify row count on EMR):"
        echo "     ./scripts/run_on_emr.sh land_registry_ingestion.py <cluster-id>"
        echo ""
        echo "  3. The conversion will create Parquet files and delete the CSV"
    else
        echo ""
        print_error "File size mismatch!"
        echo "  Local:  $LOCAL_SIZE bytes ($LOCAL_SIZE_GB GB)"
        echo "  S3:     $S3_SIZE bytes ($S3_SIZE_GB GB)"
        echo "  Diff:   $((S3_SIZE - LOCAL_SIZE)) bytes"
        echo ""
        print_warning "The upload may have failed. Try uploading again."
        exit 1
    fi
else
    print_error "Upload failed"
    exit 1
fi

