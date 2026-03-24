# Terraform Infrastructure for Land Registry Analysis

This directory contains Terraform configuration for provisioning AWS infrastructure to process UK Land Registry data using EMR and Spark.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         AWS Cloud                            │
│                                                              │
│  ┌──────────────┐      ┌─────────────────────────────────┐ │
│  │  S3 Bucket   │◄─────┤      EMR Cluster                │ │
│  │              │      │                                  │ │
│  │ - raw/       │      │  ┌──────────┐  ┌──────────┐    │ │
│  │ - scripts/   │      │  │  Master  │  │  Core 1  │    │ │
│  │ - processed/ │      │  │  Node    │  │  Node    │    │ │
│  │ - results/   │      │  └──────────┘  └──────────┘    │ │
│  └──────────────┘      │                                  │ │
│                        │  ┌──────────┐                   │ │
│  ┌──────────────┐      │  │  Core 2  │                   │ │
│  │  IAM Roles   │◄─────┤  │  Node    │                   │ │
│  │              │      │  └──────────┘                   │ │
│  │ - Service    │      │                                  │ │
│  │ - EC2        │      │  Spark 3.4 + Hadoop 3.3         │ │
│  │ - AutoScale  │      └─────────────────────────────────┘ │
│  └──────────────┘                                          │
│                                                              │
│  ┌──────────────┐                                          │
│  │ Security     │                                          │
│  │ Groups       │                                          │
│  └──────────────┘                                          │
└─────────────────────────────────────────────────────────────┘
```

## Resources Created

### Core Infrastructure
- **S3 Bucket**: Data storage with versioning and encryption
- **EMR Cluster**: Spark cluster for data processing
- **IAM Roles**: Service role, EC2 role, and auto-scaling role
- **Security Groups**: Network security for master and core nodes

### Default Configuration
- **Region**: eu-west-2 (London)
- **EMR Version**: 6.15.0 (Spark 3.4, Hadoop 3.3)
- **Master Node**: 1x m5.xlarge (4 vCPU, 16 GB RAM)
- **Core Nodes**: 2x m5.xlarge (4 vCPU, 16 GB RAM each)
- **Total Capacity**: 12 vCPU, 48 GB RAM

## Quick Start

### 1. Prerequisites

```bash
# Install Terraform
brew install terraform  # macOS
# or download from https://www.terraform.io/downloads

# Verify installation
terraform version

# Configure AWS CLI
aws configure
```

### 2. Configure Variables

```bash
# Copy example configuration
cp terraform.tfvars.example terraform.tfvars

# Edit with your settings
nano terraform.tfvars
```

### 3. Initialize Terraform

```bash
cd terraform
terraform init
```

### 4. Review Plan

```bash
# See what will be created
terraform plan
```

### 5. Create Infrastructure

```bash
# Create all resources
terraform apply

# Review the plan and type 'yes' to confirm
```

### 6. Get Cluster Information

```bash
# Get cluster ID
terraform output emr_cluster_id

# Get all outputs
terraform output

# Get specific output
terraform output -raw emr_cluster_id
```

## File Structure

```
terraform/
├── main.tf                    # Main configuration and EMR cluster
├── iam.tf                     # IAM roles and policies
├── security_groups.tf         # Security groups for EMR
├── variables.tf               # Variable definitions
├── outputs.tf                 # Output values
├── terraform.tfvars.example   # Example configuration
└── README.md                  # This file
```

## Configuration Options

### Instance Types

| Type | vCPU | RAM | Use Case | Cost/Hour* |
|------|------|-----|----------|------------|
| m5.large | 2 | 8 GB | Development | ~$0.10 |
| m5.xlarge | 4 | 16 GB | Standard | ~$0.20 |
| m5.2xlarge | 8 | 32 GB | Production | ~$0.40 |
| m5.4xlarge | 16 | 64 GB | Large datasets | ~$0.80 |

*Approximate costs for eu-west-2 region

### Cost Optimization

**Development Setup** (Lower cost):
```hcl
master_instance_type = "m5.large"
core_instance_type   = "m5.large"
core_instance_count  = 1
auto_terminate_idle_seconds = 3600  # Auto-terminate after 1 hour
```

**Production Setup** (Better performance):
```hcl
master_instance_type = "m5.2xlarge"
core_instance_type   = "m5.2xlarge"
core_instance_count  = 4
keep_cluster_alive   = false  # Terminate after jobs
```

## Usage Examples

### Run Preflight Check

```bash
# Get cluster ID
CLUSTER_ID=$(terraform output -raw emr_cluster_id)

# Run preflight check
../scripts/preflight_check.sh $CLUSTER_ID
```

### Run Ingestion Script

```bash
# Get cluster ID
CLUSTER_ID=$(terraform output -raw emr_cluster_id)

# Run ingestion
../scripts/run_on_emr.sh land_registry_ingestion.py $CLUSTER_ID
```

### SSH to Master Node

```bash
# Enable SSH in terraform.tfvars:
# allow_ssh = true
# ssh_cidr_blocks = ["YOUR_IP/32"]

# Apply changes
terraform apply

# SSH to master
terraform output -raw ssh_command
```

## Maintenance

### Update Cluster

```bash
# Modify terraform.tfvars or *.tf files
# Review changes
terraform plan

# Apply changes
terraform apply
```

### Destroy Infrastructure

```bash
# WARNING: This will delete all resources
terraform destroy

# Type 'yes' to confirm
```

### View State

```bash
# List all resources
terraform state list

# Show specific resource
terraform state show aws_emr_cluster.land_registry
```

## Troubleshooting

### Issue: "Error creating EMR cluster"

**Solution**: Check IAM roles exist and have correct permissions
```bash
aws iam get-role --role-name emr-land-registry-service-role
aws iam get-role --role-name emr-land-registry-ec2-role
```

### Issue: "Cluster stuck in STARTING state"

**Solution**: Check CloudWatch logs or EMR console for details
```bash
aws emr describe-cluster --cluster-id j-XXXXXXXXXXXXX
```

### Issue: "S3 bucket already exists"

**Solution**: Either use existing bucket or choose different name
```hcl
# In terraform.tfvars
s3_bucket_name = "landregistryproject-yourname"
```

## Security Best Practices

1. **Never commit terraform.tfvars** - Contains sensitive configuration
2. **Use least privilege IAM policies** - Only grant necessary permissions
3. **Enable termination protection** - For production clusters
4. **Restrict SSH access** - Only from your IP address
5. **Enable S3 encryption** - Already configured by default
6. **Use VPC endpoints** - For better security (optional)

## Cost Monitoring

```bash
# Estimate monthly cost
# 2x m5.xlarge core + 1x m5.xlarge master = ~$450/month (24/7)
# With auto-termination after 8 hours/day = ~$150/month

# Check current cluster cost
aws ce get-cost-and-usage \
  --time-period Start=2024-03-01,End=2024-03-24 \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --filter file://emr-filter.json
```

## Additional Resources

- [AWS EMR Documentation](https://docs.aws.amazon.com/emr/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [EMR Best Practices](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan.html)

