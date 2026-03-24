#!/bin/bash

################################################################################
# EMR Script Runner
################################################################################
# This script uploads Python scripts to S3 and submits them as EMR steps.
#
# Usage:
#   ./scripts/run_on_emr.sh <script_name> <cluster_id>
#
# Examples:
#   ./scripts/run_on_emr.sh transaction_groupby.py j-XXXXXXXXXXXXX
#   ./scripts/run_on_emr.sh preprocessing_qa.py j-XXXXXXXXXXXXX
#
# Prerequisites:
#   - AWS CLI configured with appropriate credentials
#   - Active EMR cluster with Spark installed
#   - S3 bucket: s3://landregistryproject/
#
################################################################################

set -e  # Exit on error

# Configuration
S3_BUCKET="s3://landregistryproject"
S3_SCRIPTS_PATH="${S3_BUCKET}/scripts"
LOCAL_SCRIPTS_DIR="src"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check arguments
if [ $# -lt 2 ]; then
    print_error "Usage: $0 <script_name> <cluster_id>"
    echo ""
    echo "Examples:"
    echo "  $0 transaction_groupby.py j-XXXXXXXXXXXXX"
    echo "  $0 preprocessing_qa.py j-XXXXXXXXXXXXX"
    exit 1
fi

SCRIPT_NAME=$1
CLUSTER_ID=$2

# Validate script exists
SCRIPT_PATH="${LOCAL_SCRIPTS_DIR}/${SCRIPT_NAME}"
if [ ! -f "$SCRIPT_PATH" ]; then
    print_error "Script not found: $SCRIPT_PATH"
    exit 1
fi

print_info "Script found: $SCRIPT_PATH"

# Upload script to S3
print_info "Uploading script to S3..."
aws s3 cp "$SCRIPT_PATH" "${S3_SCRIPTS_PATH}/${SCRIPT_NAME}"

if [ $? -eq 0 ]; then
    print_info "✓ Uploaded to ${S3_SCRIPTS_PATH}/${SCRIPT_NAME}"
else
    print_error "Failed to upload script to S3"
    exit 1
fi

# Check if pyspark_functions.py is needed and upload it
if grep -q "import pyspark_functions" "$SCRIPT_PATH"; then
    print_info "Script imports pyspark_functions.py, uploading dependency..."
    aws s3 cp "${LOCAL_SCRIPTS_DIR}/pyspark_functions.py" "${S3_SCRIPTS_PATH}/pyspark_functions.py"
    print_info "✓ Uploaded pyspark_functions.py"
fi

# Submit EMR step
print_info "Submitting EMR step..."
STEP_ID=$(aws emr add-steps \
    --cluster-id "$CLUSTER_ID" \
    --steps Type=Spark,Name="Run ${SCRIPT_NAME}",ActionOnFailure=CONTINUE,Args=[--deploy-mode,cluster,--master,yarn,${S3_SCRIPTS_PATH}/${SCRIPT_NAME}] \
    --query 'StepIds[0]' \
    --output text)

if [ $? -eq 0 ]; then
    print_info "✓ Step submitted successfully"
    print_info "Step ID: $STEP_ID"
    print_info "Cluster ID: $CLUSTER_ID"
    echo ""
    print_info "Monitor step status with:"
    echo "  aws emr describe-step --cluster-id $CLUSTER_ID --step-id $STEP_ID"
    echo ""
    print_info "View logs in AWS Console:"
    echo "  https://console.aws.amazon.com/emr/home?region=eu-west-2#/clusterDetails/$CLUSTER_ID"
else
    print_error "Failed to submit EMR step"
    exit 1
fi

# Optional: Wait for step completion
read -p "Wait for step to complete? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "Waiting for step to complete..."
    aws emr wait step-complete --cluster-id "$CLUSTER_ID" --step-id "$STEP_ID"
    
    # Get final status
    STATUS=$(aws emr describe-step --cluster-id "$CLUSTER_ID" --step-id "$STEP_ID" --query 'Step.Status.State' --output text)
    
    if [ "$STATUS" == "COMPLETED" ]; then
        print_info "✓ Step completed successfully!"
    else
        print_error "Step failed with status: $STATUS"
        exit 1
    fi
fi

