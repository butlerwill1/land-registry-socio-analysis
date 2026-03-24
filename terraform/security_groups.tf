################################################################################
# Security Groups for EMR
################################################################################

################################################################################
# EMR Master Security Group
################################################################################

resource "aws_security_group" "emr_master" {
  name        = "${var.cluster_name}-master-sg"
  description = "Security group for EMR master node"
  vpc_id      = data.aws_vpc.default.id

  # Automatically revoke all rules before deleting to avoid circular dependency issues
  revoke_rules_on_delete = true

  tags = {
    Name = "EMR Master Security Group"
  }
}

# Allow SSH from your IP (optional - for debugging)
resource "aws_security_group_rule" "emr_master_ssh" {
  count = var.allow_ssh ? 1 : 0
  
  type              = "ingress"
  from_port         = 22
  to_port           = 22
  protocol          = "tcp"
  cidr_blocks       = var.ssh_cidr_blocks
  security_group_id = aws_security_group.emr_master.id
  description       = "SSH access to master node"
}

# Allow all outbound traffic
resource "aws_security_group_rule" "emr_master_egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.emr_master.id
  description       = "Allow all outbound traffic"
}

# Allow communication between master and slave nodes
resource "aws_security_group_rule" "emr_master_to_slave" {
  type                     = "ingress"
  from_port                = 0
  to_port                  = 65535
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.emr_slave.id
  security_group_id        = aws_security_group.emr_master.id
  description              = "Allow traffic from slave nodes"
}

################################################################################
# EMR Slave Security Group
################################################################################

resource "aws_security_group" "emr_slave" {
  name        = "${var.cluster_name}-slave-sg"
  description = "Security group for EMR slave nodes"
  vpc_id      = data.aws_vpc.default.id

  # Automatically revoke all rules before deleting to avoid circular dependency issues
  revoke_rules_on_delete = true

  tags = {
    Name = "EMR Slave Security Group"
  }
}

# Allow all outbound traffic
resource "aws_security_group_rule" "emr_slave_egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.emr_slave.id
  description       = "Allow all outbound traffic"
}

# Allow communication between slave and master nodes
resource "aws_security_group_rule" "emr_slave_to_master" {
  type                     = "ingress"
  from_port                = 0
  to_port                  = 65535
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.emr_master.id
  security_group_id        = aws_security_group.emr_slave.id
  description              = "Allow traffic from master node"
}

# Allow communication between slave nodes
resource "aws_security_group_rule" "emr_slave_to_slave" {
  type              = "ingress"
  from_port         = 0
  to_port           = 65535
  protocol          = "tcp"
  self              = true
  security_group_id = aws_security_group.emr_slave.id
  description       = "Allow traffic between slave nodes"
}

