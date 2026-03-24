#!/bin/bash

################################################################################
# Terraform Setup Script
################################################################################
# This script helps you set up Terraform for the first time
#
# Usage:
#   cd terraform
#   ./setup.sh
#
################################################################################

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${BLUE}======================================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}======================================================================${NC}"
}

print_step() {
    echo -e "${GREEN}[STEP]${NC} $1"
}

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_header "TERRAFORM SETUP FOR LAND REGISTRY PROJECT"

# ============================================================================
# Step 1: Check Prerequisites
# ============================================================================
print_step "1. Checking prerequisites..."

if ! command -v terraform &> /dev/null; then
    echo "❌ Terraform is not installed"
    echo ""
    echo "Install it with:"
    echo "  macOS:   brew install terraform"
    echo "  Linux:   https://www.terraform.io/downloads"
    exit 1
fi

TERRAFORM_VERSION=$(terraform version -json | grep -o '"terraform_version":"[^"]*"' | cut -d'"' -f4)
print_info "Terraform installed: v$TERRAFORM_VERSION"

if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed"
    exit 1
fi

print_info "AWS CLI installed: $(aws --version 2>&1 | cut -d' ' -f1)"

if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS credentials not configured"
    echo ""
    echo "Configure with:"
    echo "  aws configure"
    exit 1
fi

AWS_ACCOUNT=$(aws sts get-caller-identity --query 'Account' --output text)
print_info "AWS Account: $AWS_ACCOUNT"

# ============================================================================
# Step 2: Create terraform.tfvars
# ============================================================================
print_step "2. Creating terraform.tfvars..."

if [ -f "terraform.tfvars" ]; then
    print_warning "terraform.tfvars already exists. Skipping."
else
    cp terraform.tfvars.example terraform.tfvars
    print_info "Created terraform.tfvars from example"
    echo ""
    echo "📝 Review and customize terraform.tfvars:"
    echo "   - Instance types (m5.large for dev, m5.xlarge for prod)"
    echo "   - Number of core nodes"
    echo "   - Auto-termination settings"
    echo ""
    read -p "Press Enter to continue..."
fi

# ============================================================================
# Step 3: Initialize Terraform
# ============================================================================
print_step "3. Initializing Terraform..."

terraform init

print_info "Terraform initialized successfully"

# ============================================================================
# Step 4: Validate Configuration
# ============================================================================
print_step "4. Validating configuration..."

terraform validate

print_info "Configuration is valid"

# ============================================================================
# Step 5: Show Plan
# ============================================================================
print_step "5. Generating execution plan..."

echo ""
echo "This will show you what resources will be created:"
echo ""

terraform plan

# ============================================================================
# Summary
# ============================================================================
print_header "SETUP COMPLETE"

echo ""
echo "✅ Terraform is ready to use!"
echo ""
echo "Next steps:"
echo ""
echo "1. Review the plan above"
echo ""
echo "2. Create the infrastructure:"
echo "   terraform apply"
echo ""
echo "3. Get the cluster ID:"
echo "   terraform output emr_cluster_id"
echo ""
echo "4. Run preflight check:"
echo "   cd .."
echo "   ./scripts/preflight_check.sh \$(cd terraform && terraform output -raw emr_cluster_id)"
echo ""
echo "5. Upload CSV and run ingestion:"
echo "   ./scripts/upload_csv_to_s3.sh"
echo "   ./scripts/run_on_emr.sh land_registry_ingestion.py \$(cd terraform && terraform output -raw emr_cluster_id)"
echo ""
echo "💡 Tip: To destroy all resources later, run:"
echo "   terraform destroy"
echo ""

