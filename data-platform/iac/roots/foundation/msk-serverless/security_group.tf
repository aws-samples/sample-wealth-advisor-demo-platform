resource "aws_security_group" "msk_primary" {
  name        = "${var.APP}-${var.ENV}-msk-sg"
  description = "Security group for MSK cluster"
  vpc_id      = local.VPC_ID
  tags = {
    Name        = "${var.APP}-${var.ENV}-msk-sg"
    Environment = var.ENV
    Application = var.APP
    Usage       = "msk"
  }
}

resource "aws_vpc_security_group_ingress_rule" "rule_1" {
  security_group_id = aws_security_group.msk_primary.id
  cidr_ipv4         = data.aws_vpc.vpc.cidr_block
  from_port         = 9092
  ip_protocol       = "tcp"
  to_port           = 9092
}

resource "aws_vpc_security_group_ingress_rule" "rule_2" {
  security_group_id = aws_security_group.msk_primary.id
  cidr_ipv4         = data.aws_vpc.vpc.cidr_block
  from_port         = 9098
  ip_protocol       = "tcp"
  to_port           = 9098
}

resource "aws_vpc_security_group_ingress_rule" "rule_3" {
  security_group_id = aws_security_group.msk_primary.id
  cidr_ipv4         = data.aws_vpc.vpc.cidr_block
  from_port         = 9094
  ip_protocol       = "tcp"
  to_port           = 9094
}

resource "aws_vpc_security_group_ingress_rule" "rule_4" {
  security_group_id = aws_security_group.msk_primary.id
  cidr_ipv4         = data.aws_vpc.vpc.cidr_block
  from_port         = 2181
  ip_protocol       = "tcp"
  to_port           = 2181
}

resource "aws_vpc_security_group_ingress_rule" "rule_5" {
  security_group_id = aws_security_group.msk_primary.id
  cidr_ipv4         = data.aws_vpc.vpc.cidr_block
  from_port         = 11001
  ip_protocol       = "tcp"
  to_port           = 11001
}

resource "aws_vpc_security_group_ingress_rule" "rule_6" {
  security_group_id = aws_security_group.msk_primary.id
  cidr_ipv4         = data.aws_vpc.vpc.cidr_block
  from_port         = 11002
  ip_protocol       = "tcp"
  to_port           = 11002
}

resource "aws_vpc_security_group_ingress_rule" "rule_7" {
  security_group_id = aws_security_group.msk_primary.id
  cidr_ipv4         = data.aws_vpc.vpc.cidr_block
  from_port         = 0
  ip_protocol       = "tcp"
  to_port           = 65535
}

resource "aws_vpc_security_group_ingress_rule" "rule_8" {
  security_group_id            = aws_security_group.msk_primary.id
  referenced_security_group_id = local.VPC_SECURITY_GROUP
  from_port                    = 0
  ip_protocol                  = "tcp"
  to_port                      = 65535
}

resource "aws_vpc_security_group_ingress_rule" "rule_9" {
  ip_protocol                  = "tcp"
  security_group_id            = aws_security_group.msk_primary.id
  from_port                    = 0
  to_port                      = 65535
  referenced_security_group_id = aws_security_group.msk_client_sg.id
}

resource "aws_vpc_security_group_ingress_rule" "rule10" {
  ip_protocol                  = "tcp"
  security_group_id            = aws_security_group.msk_primary.id
  from_port                    = 0
  to_port                      = 65535
  referenced_security_group_id = aws_security_group.lambda_sg.id

  # lambda_sg uses create_before_destroy (name_prefix causes replacement).
  # This rule must also use create_before_destroy so the new rule referencing
  # the new lambda_sg is created before the old rule is deleted, releasing the
  # hold on the old lambda_sg and allowing it to be destroyed cleanly.
  lifecycle {
    create_before_destroy = true
  }
}


resource "aws_vpc_security_group_egress_rule" "erule_1" {
  ip_protocol       = "-1"
  security_group_id = aws_security_group.msk_primary.id
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_ssm_parameter" "msk_sg_primary" {
  name        = "/${var.APP}/${var.ENV}/msk-sg"
  description = "The MSK security group"
  type        = "SecureString"
  value       = aws_security_group.msk_primary.id
  key_id      = data.aws_kms_key.ssm_kms_key.arn
  overwrite   = true

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage       = "msk"
  }
}
