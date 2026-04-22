// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

resource "aws_security_group" "sagemaker_sg" {

  name        = "${var.APP}-${var.ENV}-sagemaker-vpc-endpoint-sg"
  description = "Security group for SageMaker Unified Studio VPC Endpoints"
  vpc_id      = aws_vpc.main.id

  egress {
    description = "Allows outbound HTTPS access to any IPv4 address"
    protocol    = "tcp"
    from_port   = 443
    to_port     = 443
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Allows inbound HTTPS access for traffic from VPC"
    protocol    = "tcp"
    from_port   = 443
    to_port     = 443
    cidr_blocks = [aws_vpc.main.cidr_block]
  }

  tags = {
    Name                                    = "${var.APP}-${var.ENV}-sagemaker-vpc-endpoint-sg"
    Application                             = var.APP
    Environment                             = var.ENV
  }
  #checkov:skip=CKV2_AWS_5: "Ensure that Security Groups are attached to another resource": "Skipping this the security group is already attached to the VPC"
}

resource "aws_security_group" "vpc_sg" {

  name        = "${var.APP}-${var.ENV}-vpc-sg"
  description = "${var.APP}-${var.ENV}-vpc-sg"
  vpc_id      = aws_vpc.main.id

  ingress {
    description       = "Allow all traffic From VPC"
    from_port         = 0
    to_port           = 65535
    protocol          = "tcp"
    cidr_blocks       = [aws_vpc.main.cidr_block]
  }

  ingress {
    description       = "Self"
    from_port         = 0
    to_port           = 65535
    protocol          = "tcp"
    self              = true
  }

  egress {
    description       = "Egress Ports"
    from_port         = 0
    to_port           = 0
    protocol          = "-1"
    cidr_blocks       = ["0.0.0.0/0"]
  }

  tags = {
    Application = var.APP
    Environment = var.ENV
    Name = "${var.APP}-${var.ENV}-vpc-sg"
  }

  #checkov:skip=CKV2_AWS_5: "Ensure that Security Groups are attached to another resource"
  #checkov:skip=CKV_AWS_382: "Ensure no security groups allow egress from 0.0.0.0:0 to port -1": "Skipping this for simplicity"
}

resource "aws_ssm_parameter" "vpc_sg_ssm" {

  name        = "/${var.APP}/${var.ENV}/vpc-sg"
  description = "The VPC security group"
  type        = "SecureString"
  value       = aws_security_group.vpc_sg.id
  key_id      = data.aws_kms_key.ssm_kms_key.key_id
  overwrite   = true

  tags = {
    Application = var.APP
    Environment = var.ENV
  }
}