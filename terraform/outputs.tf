################################################################################
# Outputs
################################################################################

output "emr_cluster_id" {
  description = "ID of the EMR cluster"
  value       = aws_emr_cluster.land_registry.id
}

output "emr_cluster_name" {
  description = "Name of the EMR cluster"
  value       = aws_emr_cluster.land_registry.name
}

output "emr_cluster_state" {
  description = "State of the EMR cluster"
  value       = aws_emr_cluster.land_registry.cluster_state
}

output "emr_master_public_dns" {
  description = "Public DNS of the EMR master node"
  value       = aws_emr_cluster.land_registry.master_public_dns
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket"
  value       = data.aws_s3_bucket.data_bucket.id
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = data.aws_s3_bucket.data_bucket.arn
}

output "emr_service_role_arn" {
  description = "ARN of the EMR service role"
  value       = aws_iam_role.emr_service_role.arn
}

output "emr_ec2_role_arn" {
  description = "ARN of the EMR EC2 instance role"
  value       = aws_iam_role.emr_ec2_role.arn
}

output "emr_instance_profile_arn" {
  description = "ARN of the EMR EC2 instance profile"
  value       = aws_iam_instance_profile.emr_ec2_instance_profile.arn
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group for EMR logs"
  value       = var.enable_cloudwatch_logs ? aws_cloudwatch_log_group.emr_logs[0].name : "CloudWatch logs disabled"
}

output "cloudwatch_logs_url" {
  description = "URL to view CloudWatch logs in AWS Console"
  value       = var.enable_cloudwatch_logs ? "https://console.aws.amazon.com/cloudwatch/home?region=${data.aws_region.current.name}#logsV2:log-groups/log-group/${replace(aws_cloudwatch_log_group.emr_logs[0].name, "/", "$252F")}" : "CloudWatch logs disabled"
}

################################################################################
# Helpful Commands
################################################################################

output "ssh_command" {
  description = "SSH command to connect to master node (if SSH is enabled)"
  value       = var.allow_ssh ? "ssh -i ~/.ssh/your-key.pem hadoop@${aws_emr_cluster.land_registry.master_public_dns}" : "SSH is disabled. Set allow_ssh = true to enable."
}

output "run_script_command" {
  description = "Example command to run a script on EMR"
  value       = "./scripts/run_on_emr.sh land_registry_ingestion.py ${aws_emr_cluster.land_registry.id}"
}

output "preflight_check_command" {
  description = "Command to run preflight check"
  value       = "./scripts/preflight_check.sh ${aws_emr_cluster.land_registry.id}"
}

