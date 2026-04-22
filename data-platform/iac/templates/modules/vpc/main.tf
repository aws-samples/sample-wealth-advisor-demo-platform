// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

terraform {
  required_providers {
    aws = {
      source                = "hashicorp/aws"
      configuration_aliases = [aws]
    }
  }
}

module "vpc" {

  source = "git::https://github.com/terraform-aws-modules/terraform-aws-vpc.git?ref=2e417ad"
  
  name = "${var.APP}-${var.ENV}-vpc"
  cidr = var.CIDR

  azs             = ["${var.AWS_REGION}a", "${var.AWS_REGION}b", "${var.AWS_REGION}c"]
  private_subnets = var.PRIVATE_SUBNETS
  public_subnets  = var.PUBLIC_SUBNETS

  create_igw         = true
  enable_nat_gateway = true

  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = var.USAGE
  }
}

resource "aws_ssm_parameter" "vpc" {

  name        = "/${var.APP}/${var.ENV}/vpc"
  description = "The VPC ID"
  type        = "SecureString"
  value       = module.vpc.vpc_id
  key_id      = var.KMS_KEY

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = var.USAGE
  }
  overwrite = true
}

resource "aws_ssm_parameter" "public_subnet_1" {

  name        = "/${var.APP}/${var.ENV}/public-subnet-1"
  description = "The Public Subnet 1"
  type        = "SecureString"
  value       = module.vpc.public_subnets[0]
  key_id      = var.KMS_KEY

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = var.USAGE
  }
  overwrite = true
}

resource "aws_ssm_parameter" "public_subnet_2" {

  name        = "/${var.APP}/${var.ENV}/public-subnet-2"
  description = "The Public Subnet 2"
  type        = "SecureString"
  value       = module.vpc.public_subnets[1]
  key_id      = var.KMS_KEY

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = var.USAGE
  }
  overwrite = true
}

resource "aws_ssm_parameter" "public_subnet_3" {

  name        = "/${var.APP}/${var.ENV}/public-subnet-3"
  description = "The Public Subnet 3"
  type        = "SecureString"
  value       = module.vpc.public_subnets[2]
  key_id      = var.KMS_KEY

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = var.USAGE
  }
  overwrite = true
}

resource "aws_ssm_parameter" "private_subnet_1" {

  name        = "/${var.APP}/${var.ENV}/private-subnet-1"
  description = "The Private Subnet 1"
  type        = "SecureString"
  value       = module.vpc.private_subnets[0]
  key_id      = var.KMS_KEY

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = var.USAGE
  }
  overwrite = true
}

resource "aws_ssm_parameter" "private_subnet_2" {

  name        = "/${var.APP}/${var.ENV}/private-subnet-2"
  description = "The Private Subnet 2"
  type        = "SecureString"
  value       = module.vpc.private_subnets[1]
  key_id      = var.KMS_KEY

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = var.USAGE
  }
  overwrite = true
}

resource "aws_ssm_parameter" "private_subnet_3" {

  name        = "/${var.APP}/${var.ENV}/private-subnet-3"
  description = "The Private Subnet 3"
  type        = "SecureString"
  value       = module.vpc.private_subnets[2]
  key_id      = var.KMS_KEY

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = var.USAGE
  }
  overwrite = true
}

data "aws_route_table" "public_subnet_1_route_table" {

  subnet_id = module.vpc.public_subnets[0]
}

data "aws_route_table" "private_subnet_1_route_table" {

  subnet_id = module.vpc.private_subnets[0]
}

data "aws_route_table" "private_subnet_2_route_table" {

  subnet_id = module.vpc.private_subnets[1]
}

data "aws_route_table" "private_subnet_3_route_table" {

  subnet_id = module.vpc.private_subnets[2]
}

resource "aws_ssm_parameter" "public_subnet_1_route_table_id" {

  name        = "/${var.APP}/${var.ENV}/public-subnet-1-route-table-id"
  description = "The Public Subnet 1 Route Table ID"
  type        = "SecureString"
  value       = data.aws_route_table.public_subnet_1_route_table.id
  key_id      = var.KMS_KEY

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = var.USAGE
  }
  overwrite = true
}

resource "aws_ssm_parameter" "private_subnet_1_route_table_id" {

  name        = "/${var.APP}/${var.ENV}/private-subnet-1-route-table-id"
  description = "The Private Subnet 1 Route Table ID"
  type        = "SecureString"
  value       = data.aws_route_table.private_subnet_1_route_table.id
  key_id      = var.KMS_KEY

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = var.USAGE
  }
  overwrite = true
}

resource "aws_ssm_parameter" "private_subnet_2_route_table_id" {

  name        = "/${var.APP}/${var.ENV}/private-subnet-2-route-table-id"
  description = "The Private Subnet 2 Route Table ID"
  type        = "SecureString"
  value       = data.aws_route_table.private_subnet_2_route_table.id
  key_id      = var.KMS_KEY

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = var.USAGE
  }
  overwrite = true
}

resource "aws_ssm_parameter" "private_subnet_3_route_table_id" {

  name        = "/${var.APP}/${var.ENV}/private-subnet-3-route-table-id"
  description = "The Private Subnet 3 Route Table ID"
  type        = "SecureString"
  value       = data.aws_route_table.private_subnet_3_route_table.id
  key_id      = var.KMS_KEY

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = var.USAGE
  }
  overwrite = true
}

resource "aws_security_group" "glue_sg" {

  name        = "${var.APP}-${var.ENV}-glue-sg"
  description = "${var.APP}-${var.ENV}-glue-sg"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description       = "From VPC"
    from_port         = 0
    to_port           = 65535
    protocol          = "tcp"
    cidr_blocks       = [var.CIDR]
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
    Usage = var.USAGE
    Name = "${var.APP}-${var.ENV}-glue-sg"
  }

  #checkov:skip=CKV2_AWS_5: "Ensure that Security Groups are attached to another resource"
  #checkov:skip=CKV_AWS_382: "Ensure no security groups allow egress from 0.0.0.0:0 to port -1": "Skipping this for simplicity"
}

resource "aws_ssm_parameter" "glue_sg" {

  name        = "/${var.APP}/${var.ENV}/glue-sg"
  description = "The glue security group"
  type        = "SecureString"
  value       = aws_security_group.glue_sg.id
  key_id      = var.KMS_KEY

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = var.USAGE
  }
  overwrite = true
}

resource "aws_security_group" "sagemaker-sg" {

  name        = "${var.APP}-${var.ENV}-sagemaker-sg"
  description = "${var.APP}-${var.ENV}-sagemaker-sg"
  vpc_id      = module.vpc.vpc_id

  # Example rule for HTTPS
  ingress {
    description = "HTTPS from VPC"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.CIDR]
  }

  egress {
    description = "Egress All"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = var.USAGE
    Name = "sagemaker-sg"
  }

  #checkov:skip=CKV2_AWS_5:  "Ensure that Security Groups are attached to another resource": "Security groups are created in VPC module, but used in other modules"
  #checkov:skip=CKV_AWS_382: "Ensure no security groups allow egress from 0.0.0.0:0 to port -1": "Skipping this for simplicity"
}

resource "aws_ssm_parameter" "sagemaker-sg" {

  name        = "/${var.APP}/${var.ENV}/sagemaker-sg"
  description = "The sagemaker security group"
  type        = "SecureString"
  value       = aws_security_group.sagemaker-sg.id
  key_id      = var.KMS_KEY

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = var.USAGE
  }
  overwrite = true
}
