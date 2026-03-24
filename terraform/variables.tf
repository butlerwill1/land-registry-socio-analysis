################################################################################
# Variables
################################################################################

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "eu-west-2"
}

variable "aws_profile" {
  description = "AWS CLI profile to use"
  type        = string
  default     = "default"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

################################################################################
# S3 Configuration
################################################################################

variable "s3_bucket_name" {
  description = "Name of the S3 bucket for data and scripts"
  type        = string
  default     = "landregistryproject"
}

################################################################################
# EMR Cluster Configuration
################################################################################

variable "cluster_name" {
  description = "Name of the EMR cluster"
  type        = string
  default     = "emr-land-registry"
}

variable "emr_release_label" {
  description = "EMR release version"
  type        = string
  default     = "emr-6.15.0"  # Latest stable version with Spark 3.4
}

variable "master_instance_type" {
  description = "EC2 instance type for master node"
  type        = string
  default     = "m5.xlarge"  # 4 vCPU, 16 GB RAM
}

variable "master_ebs_size" {
  description = "EBS volume size for master node (GB)"
  type        = number
  default     = 50
}

variable "core_instance_type" {
  description = "EC2 instance type for core nodes"
  type        = string
  default     = "m5.xlarge"  # 4 vCPU, 16 GB RAM
}

variable "core_instance_count" {
  description = "Number of core instances"
  type        = number
  default     = 2
}

variable "core_ebs_size" {
  description = "EBS volume size for core nodes (GB)"
  type        = number
  default     = 100
}

variable "keep_cluster_alive" {
  description = "Keep cluster running when no steps are executing"
  type        = bool
  default     = true
}

variable "termination_protection" {
  description = "Enable termination protection"
  type        = bool
  default     = false
}

variable "auto_terminate_idle_seconds" {
  description = "Auto-terminate cluster after idle time (seconds). Set to 0 to disable."
  type        = number
  default     = 0  # Disabled by default
}

################################################################################
# Security Configuration
################################################################################

variable "allow_ssh" {
  description = "Allow SSH access to master node"
  type        = bool
  default     = false
}

variable "ssh_cidr_blocks" {
  description = "CIDR blocks allowed to SSH to master node"
  type        = list(string)
  default     = []  # Add your IP: ["1.2.3.4/32"]
}

