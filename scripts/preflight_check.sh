#!/bin/bash

################################################################################
# EMR Preflight Check for Land Registry Ingestion
################################################################################
# This script checks that everything is ready to run land_registry_ingestion.py
# on your EMR cluster.
#
# Usage:
#   ./scripts/preflight_check.sh [cluster-id]
#
################################################################################

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${BLUE}======================================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}======================================================================${NC}"
}

print_check() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

ERRORS=0
WARNINGS=0

print_header "EMR PREFLIGHT CHECK FOR LAND REGISTRY INGESTION"

# ============================================================================
# 1. Check AWS CLI
# ============================================================================
echo ""
echo "1. Checking AWS CLI..."
if command -v aws &> /dev/null; then
    AWS_VERSION=$(aws --version 2>&1 | cut -d' ' -f1)
    print_check "AWS CLI installed: $AWS_VERSION"
else
    print_error "AWS CLI not installed"
    ((ERRORS++))
fi

# ============================================================================
# 2. Check AWS Credentials
# ============================================================================
echo ""
echo "2. Checking AWS credentials..."
if aws sts get-caller-identity &> /dev/null; then
    AWS_ACCOUNT=$(aws sts get-caller-identity --query 'Account' --output text)
    AWS_REGION=$(aws configure get region)
    print_check "AWS credentials configured"
    echo "   Account: $AWS_ACCOUNT"
    echo "   Region: $AWS_REGION"
    
    # Check if region matches Terraform
    if [ "$AWS_REGION" != "us-east-1" ]; then
        print_warning "AWS CLI region ($AWS_REGION) differs from Terraform (us-east-1)"
        echo "   Update emr_cluster.tf or run: aws configure set region us-east-1"
        ((WARNINGS++))
    fi
else
    print_error "AWS credentials not configured"
    echo "   Run: aws configure"
    ((ERRORS++))
fi

# ============================================================================
# 3. Check S3 Bucket
# ============================================================================
echo ""
echo "3. Checking S3 bucket..."
S3_BUCKET="landregistryproject"

if aws s3 ls "s3://$S3_BUCKET" &> /dev/null; then
    print_check "S3 bucket exists: s3://$S3_BUCKET"
    
    # Check bucket region
    BUCKET_REGION=$(aws s3api get-bucket-location --bucket "$S3_BUCKET" --query 'LocationConstraint' --output text)
    if [ "$BUCKET_REGION" == "None" ]; then
        BUCKET_REGION="us-east-1"
    fi
    echo "   Bucket region: $BUCKET_REGION"
    
    if [ "$BUCKET_REGION" != "us-east-1" ]; then
        print_warning "Bucket region ($BUCKET_REGION) differs from EMR cluster region (us-east-1)"
        echo "   This may cause performance issues. Consider updating emr_cluster.tf region."
        ((WARNINGS++))
    fi
else
    print_error "S3 bucket does not exist: s3://$S3_BUCKET"
    echo "   Create it with: aws s3 mb s3://$S3_BUCKET --region us-east-1"
    ((ERRORS++))
fi

# ============================================================================
# 4. Check CSV File in S3 (Bronze Layer)
# ============================================================================
echo ""
echo "4. Checking CSV file in S3 (bronze layer)..."
CSV_KEY="bronze/land_registry_data.csv"

if aws s3 ls "s3://$S3_BUCKET/$CSV_KEY" &> /dev/null; then
    CSV_SIZE=$(aws s3api head-object --bucket "$S3_BUCKET" --key "$CSV_KEY" --query 'ContentLength' --output text)
    CSV_SIZE_GB=$(echo "scale=2; $CSV_SIZE / 1024 / 1024 / 1024" | bc)
    print_check "CSV file exists: s3://$S3_BUCKET/$CSV_KEY"
    echo "   Size: $CSV_SIZE bytes ($CSV_SIZE_GB GB)"
    
    if [ "$CSV_SIZE" -lt 1000000000 ]; then
        print_warning "CSV file seems small ($CSV_SIZE_GB GB). Expected ~5GB."
        ((WARNINGS++))
    fi
else
    print_error "CSV file not found: s3://$S3_BUCKET/$CSV_KEY"
    echo "   Upload it with: ./scripts/upload_csv_to_s3.sh"
    ((ERRORS++))
fi

# ============================================================================
# 5. Check Scripts in S3
# ============================================================================
echo ""
echo "5. Checking scripts in S3..."
SCRIPT_KEY="scripts/land_registry_ingestion.py"

if aws s3 ls "s3://$S3_BUCKET/$SCRIPT_KEY" &> /dev/null; then
    print_check "Ingestion script exists: s3://$S3_BUCKET/$SCRIPT_KEY"
else
    print_warning "Ingestion script not in S3 yet"
    echo "   It will be uploaded automatically when you run: ./scripts/run_on_emr.sh"
    ((WARNINGS++))
fi

# ============================================================================
# 6. Check EMR Cluster (if cluster ID provided)
# ============================================================================
CLUSTER_ID="${1:-}"

if [ -n "$CLUSTER_ID" ]; then
    echo ""
    echo "6. Checking EMR cluster: $CLUSTER_ID..."

    if CLUSTER_INFO=$(aws emr describe-cluster --cluster-id "$CLUSTER_ID" 2>&1); then
        CLUSTER_STATE=$(echo "$CLUSTER_INFO" | grep -o '"State": "[^"]*"' | head -1 | cut -d'"' -f4)
        CLUSTER_NAME=$(echo "$CLUSTER_INFO" | grep -o '"Name": "[^"]*"' | head -1 | cut -d'"' -f4)

        print_check "Cluster exists: $CLUSTER_NAME"
        echo "   State: $CLUSTER_STATE"

        if [ "$CLUSTER_STATE" == "WAITING" ]; then
            print_check "Cluster is ready to accept jobs"
        elif [ "$CLUSTER_STATE" == "RUNNING" ]; then
            print_check "Cluster is running"
        elif [ "$CLUSTER_STATE" == "STARTING" ]; then
            print_warning "Cluster is still starting. Wait for WAITING state."
            ((WARNINGS++))
        else
            print_error "Cluster state is $CLUSTER_STATE (expected WAITING or RUNNING)"
            ((ERRORS++))
        fi

        # Check applications
        if echo "$CLUSTER_INFO" | grep -q "Spark"; then
            print_check "Spark is installed"
        else
            print_error "Spark is not installed on cluster"
            ((ERRORS++))
        fi

        if echo "$CLUSTER_INFO" | grep -q "Hadoop"; then
            print_check "Hadoop is installed"
        else
            print_error "Hadoop is not installed on cluster"
            ((ERRORS++))
        fi

    else
        print_error "Cannot access cluster: $CLUSTER_ID"
        echo "   Error: $CLUSTER_INFO"
        ((ERRORS++))
    fi
else
    echo ""
    echo "6. EMR cluster check skipped (no cluster ID provided)"
    print_warning "Provide cluster ID to check: ./scripts/preflight_check.sh <cluster-id>"
    ((WARNINGS++))
fi

# ============================================================================
# 7. Check Terraform Configuration
# ============================================================================
echo ""
echo "7. Checking Terraform configuration..."

if [ -d "terraform" ]; then
    print_check "Terraform directory exists"

    # Check if main.tf exists
    if [ -f "terraform/main.tf" ]; then
        print_check "Terraform configuration found: terraform/main.tf"

        # Check region from variables
        if [ -f "terraform/variables.tf" ]; then
            TF_REGION=$(grep 'default.*=.*"eu-west-' terraform/variables.tf | head -1 | cut -d'"' -f2)
            echo "   Default region: $TF_REGION"
        fi

        # Check if terraform is initialized
        if [ -d "terraform/.terraform" ]; then
            print_check "Terraform initialized"
        else
            print_warning "Terraform not initialized. Run: cd terraform && terraform init"
            ((WARNINGS++))
        fi

        # Check if tfvars exists
        if [ -f "terraform/terraform.tfvars" ]; then
            print_check "Configuration file exists: terraform.tfvars"
        else
            print_warning "terraform.tfvars not found. Copy from terraform.tfvars.example"
            echo "   Run: cp terraform/terraform.tfvars.example terraform/terraform.tfvars"
            ((WARNINGS++))
        fi

    else
        print_error "terraform/main.tf not found"
        ((ERRORS++))
    fi

elif [ -f "emr_cluster.tf" ]; then
    print_warning "Old Terraform structure detected (emr_cluster.tf in root)"
    echo "   Consider migrating to new structure in terraform/ directory"
    ((WARNINGS++))
else
    print_error "No Terraform configuration found"
    echo "   Expected: terraform/ directory with main.tf"
    ((ERRORS++))
fi

# ============================================================================
# SUMMARY
# ============================================================================
print_header "PREFLIGHT CHECK SUMMARY"

echo ""
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    print_check "All checks passed! Ready to run ingestion."
    echo ""
    echo "Next step:"
    if [ -n "$CLUSTER_ID" ]; then
        echo "  ./scripts/run_on_emr.sh land_registry_ingestion.py $CLUSTER_ID"
    else
        echo "  ./scripts/run_on_emr.sh land_registry_ingestion.py <cluster-id>"
    fi
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}Warnings: $WARNINGS${NC}"
    echo ""
    echo "You can proceed, but review the warnings above."
    echo ""
    echo "Next step:"
    if [ -n "$CLUSTER_ID" ]; then
        echo "  ./scripts/run_on_emr.sh land_registry_ingestion.py $CLUSTER_ID"
    else
        echo "  ./scripts/run_on_emr.sh land_registry_ingestion.py <cluster-id>"
    fi
else
    echo -e "${RED}Errors: $ERRORS${NC}"
    echo -e "${YELLOW}Warnings: $WARNINGS${NC}"
    echo ""
    echo "Fix the errors above before running the ingestion script."
    exit 1
fi

echo ""

