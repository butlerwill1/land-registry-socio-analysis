################################################################################
# Land Registry Analysis - EMR Infrastructure
################################################################################
# This Terraform configuration creates the AWS infrastructure for processing
# UK Land Registry data using EMR and Spark.
#
# Resources created:
#   - S3 bucket for data and scripts
#   - IAM roles and policies for EMR
#   - EMR cluster with Spark and Hadoop
#   - Security groups for EMR
#
# Usage:
#   terraform init
#   terraform plan
#   terraform apply
#
################################################################################

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile
  
  default_tags {
    tags = {
      Project     = "land-registry-analysis"
      ManagedBy   = "terraform"
      Environment = var.environment
    }
  }
}

################################################################################
# Data Sources
################################################################################

# Get current AWS account ID
data "aws_caller_identity" "current" {}

# Get current AWS region
data "aws_region" "current" {}

# Get default VPC
data "aws_vpc" "default" {
  default = true
}

# Get default subnets
data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

################################################################################
# S3 Bucket
################################################################################

resource "aws_s3_bucket" "data_bucket" {
  bucket = var.s3_bucket_name
  
  tags = {
    Name = "Land Registry Data Bucket"
  }
}

resource "aws_s3_bucket_versioning" "data_bucket" {
  bucket = aws_s3_bucket.data_bucket.id
  
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data_bucket" {
  bucket = aws_s3_bucket.data_bucket.id
  
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Block public access
resource "aws_s3_bucket_public_access_block" "data_bucket" {
  bucket = aws_s3_bucket.data_bucket.id
  
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

################################################################################
# EMR Cluster
################################################################################

resource "aws_emr_cluster" "land_registry" {
  name          = var.cluster_name
  release_label = var.emr_release_label
  applications  = ["Spark", "Hadoop", "JupyterEnterpriseGateway", "Livy"]
  
  service_role = aws_iam_role.emr_service_role.arn
  
  ec2_attributes {
    instance_profile = aws_iam_instance_profile.emr_ec2_instance_profile.arn
    
    emr_managed_master_security_group = aws_security_group.emr_master.id
    emr_managed_slave_security_group  = aws_security_group.emr_slave.id
    
    # Use first available subnet from default VPC
    subnet_id = data.aws_subnets.default.ids[0]
  }
  
  master_instance_group {
    instance_type  = var.master_instance_type
    instance_count = 1
    
    ebs_config {
      size                 = var.master_ebs_size
      type                 = "gp3"
      volumes_per_instance = 1
    }
  }
  
  core_instance_group {
    instance_type  = var.core_instance_type
    instance_count = var.core_instance_count
    
    ebs_config {
      size                 = var.core_ebs_size
      type                 = "gp3"
      volumes_per_instance = 1
    }
  }
  
  # Keep cluster running for development
  keep_job_flow_alive_when_no_steps = var.keep_cluster_alive
  
  # Termination protection
  termination_protection = var.termination_protection
  
  # Auto-termination after idle time (optional)
  auto_termination_policy {
    idle_timeout = var.auto_terminate_idle_seconds
  }
  
  tags = {
    Name    = var.cluster_name
    Purpose = "data-processing"
  }
}

