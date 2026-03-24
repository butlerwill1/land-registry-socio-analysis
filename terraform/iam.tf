################################################################################
# IAM Roles and Policies for EMR
################################################################################

################################################################################
# EMR Service Role
################################################################################

# IAM role for EMR service
resource "aws_iam_role" "emr_service_role" {
  name               = "${var.cluster_name}-service-role"
  assume_role_policy = data.aws_iam_policy_document.emr_service_assume_role.json
  
  tags = {
    Name = "EMR Service Role"
  }
}

# Trust policy for EMR service
data "aws_iam_policy_document" "emr_service_assume_role" {
  statement {
    effect = "Allow"
    
    principals {
      type        = "Service"
      identifiers = ["elasticmapreduce.amazonaws.com"]
    }
    
    actions = ["sts:AssumeRole"]
  }
}

# Attach AWS managed policy for EMR service role
resource "aws_iam_role_policy_attachment" "emr_service_role" {
  role       = aws_iam_role.emr_service_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonElasticMapReduceRole"
}

################################################################################
# EMR EC2 Instance Role
################################################################################

# IAM role for EMR EC2 instances
resource "aws_iam_role" "emr_ec2_role" {
  name               = "${var.cluster_name}-ec2-role"
  assume_role_policy = data.aws_iam_policy_document.emr_ec2_assume_role.json
  
  tags = {
    Name = "EMR EC2 Instance Role"
  }
}

# Trust policy for EC2 instances
data "aws_iam_policy_document" "emr_ec2_assume_role" {
  statement {
    effect = "Allow"
    
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
    
    actions = ["sts:AssumeRole"]
  }
}

# Attach AWS managed policy for EMR EC2 instances
resource "aws_iam_role_policy_attachment" "emr_ec2_role" {
  role       = aws_iam_role.emr_ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonElasticMapReduceforEC2Role"
}

# Attach CloudWatch Logs policy for log streaming
resource "aws_iam_role_policy_attachment" "emr_ec2_cloudwatch" {
  role       = aws_iam_role.emr_ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"
}

# Custom policy for S3 access
resource "aws_iam_role_policy" "emr_ec2_s3_access" {
  name   = "s3-access"
  role   = aws_iam_role.emr_ec2_role.id
  policy = data.aws_iam_policy_document.emr_ec2_s3_access.json
}

# S3 access policy document
data "aws_iam_policy_document" "emr_ec2_s3_access" {
  statement {
    effect = "Allow"
    
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket"
    ]
    
    resources = [
      data.aws_s3_bucket.data_bucket.arn,
      "${data.aws_s3_bucket.data_bucket.arn}/*"
    ]
  }
  
  statement {
    effect = "Allow"
    
    actions = [
      "s3:ListAllMyBuckets"
    ]
    
    resources = ["*"]
  }
}

# Instance profile for EC2 instances
resource "aws_iam_instance_profile" "emr_ec2_instance_profile" {
  name = "${var.cluster_name}-instance-profile"
  role = aws_iam_role.emr_ec2_role.name
  
  tags = {
    Name = "EMR EC2 Instance Profile"
  }
}

################################################################################
# EMR Auto Scaling Role (Optional)
################################################################################

# IAM role for EMR auto scaling
resource "aws_iam_role" "emr_autoscaling_role" {
  name               = "${var.cluster_name}-autoscaling-role"
  assume_role_policy = data.aws_iam_policy_document.emr_autoscaling_assume_role.json
  
  tags = {
    Name = "EMR Auto Scaling Role"
  }
}

# Trust policy for EMR auto scaling
data "aws_iam_policy_document" "emr_autoscaling_assume_role" {
  statement {
    effect = "Allow"
    
    principals {
      type        = "Service"
      identifiers = ["elasticmapreduce.amazonaws.com", "application-autoscaling.amazonaws.com"]
    }
    
    actions = ["sts:AssumeRole"]
  }
}

# Attach AWS managed policy for EMR auto scaling
resource "aws_iam_role_policy_attachment" "emr_autoscaling_role" {
  role       = aws_iam_role.emr_autoscaling_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonElasticMapReduceforAutoScalingRole"
}

