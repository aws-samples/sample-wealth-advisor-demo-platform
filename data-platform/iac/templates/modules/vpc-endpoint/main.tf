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

resource "aws_security_group" "vpc_endpoint_sg" {

  name        = "${var.APP}-${var.ENV}-${var.AWS_REGION}-vpc-endpoint-sg"
  description = "${var.APP}-${var.ENV}-${var.AWS_REGION}-vpc-endpoint-sg"
  vpc_id      = var.VPC_ID

  ingress {
    description = "Connect endpoints from VPC resources"
    from_port   = 0
    to_port     = 65535
    protocol    = "tcp"
    cidr_blocks = [var.CIDR]
  }

  egress {
    description = "All egress allowed"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = var.USAGE
    Name = "${var.APP}-${var.ENV}-${var.AWS_REGION}-vpc-endpoint-sg"
  }

  #checkov:skip=CKV_AWS_382: "Ensure no security groups allow egress from 0.0.0.0:0 to port -1": "Skipping this for simplicity"
}

resource "aws_vpc_endpoint" "dynamodb_endpoint" {

  vpc_id            = var.VPC_ID
  service_name      = "com.amazonaws.${var.AWS_REGION}.dynamodb"
  vpc_endpoint_type = "Gateway"
  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = var.USAGE
    Name = "dynamodb-vpc-endpoint"
  }
}

resource "aws_vpc_endpoint" "secrets_manager_endpoint" {

  vpc_id              = var.VPC_ID
  service_name        = "com.amazonaws.${var.AWS_REGION}.secretsmanager"
  vpc_endpoint_type   = "Interface"
  security_group_ids  = [aws_security_group.vpc_endpoint_sg.id]
  private_dns_enabled = true
  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = var.USAGE
    Name = "secrets-manager-vpc-endpoint"
  }
}

resource "aws_vpc_endpoint_subnet_association" "secrets_manager_endpoint_association_1" {

  vpc_endpoint_id = aws_vpc_endpoint.secrets_manager_endpoint.id
  subnet_id       = var.PUBLIC_SUBNET_1
}

resource "aws_vpc_endpoint_subnet_association" "secrets_manager_endpoint_association_2" {

  vpc_endpoint_id = aws_vpc_endpoint.secrets_manager_endpoint.id
  subnet_id       = var.PUBLIC_SUBNET_2
}

resource "aws_vpc_endpoint_subnet_association" "secrets_manager_endpoint_association_3" {

  vpc_endpoint_id = aws_vpc_endpoint.secrets_manager_endpoint.id
  subnet_id       = var.PUBLIC_SUBNET_3
}

resource "aws_vpc_endpoint" "ssm_endpoint" {

  vpc_id              = var.VPC_ID
  service_name        = "com.amazonaws.${var.AWS_REGION}.ssm"
  vpc_endpoint_type   = "Interface"
  security_group_ids  = [aws_security_group.vpc_endpoint_sg.id]
  private_dns_enabled = true
  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = var.USAGE
    Name = "ssm-vpc-endpoint"
  }
}

resource "aws_vpc_endpoint_subnet_association" "ssm_endpoint_association_1" {

  vpc_endpoint_id = aws_vpc_endpoint.ssm_endpoint.id
  subnet_id       = var.PUBLIC_SUBNET_1
}

resource "aws_vpc_endpoint_subnet_association" "ssm_endpoint_association_2" {

  vpc_endpoint_id = aws_vpc_endpoint.ssm_endpoint.id
  subnet_id       = var.PUBLIC_SUBNET_2
}

resource "aws_vpc_endpoint_subnet_association" "ssm_endpoint_association_3" {

  vpc_endpoint_id = aws_vpc_endpoint.ssm_endpoint.id
  subnet_id       = var.PUBLIC_SUBNET_3
}

resource "aws_vpc_endpoint" "execute_api_endpoint" {

  vpc_id              = var.VPC_ID
  service_name        = "com.amazonaws.${var.AWS_REGION}.execute-api"
  vpc_endpoint_type   = "Interface"
  security_group_ids  = [aws_security_group.vpc_endpoint_sg.id]
  private_dns_enabled = true
  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = var.USAGE
    Name = "execute-api-vpc-endpoint"
  }
}

resource "aws_vpc_endpoint_subnet_association" "execute_api_endpoint_association_1" {

  vpc_endpoint_id = aws_vpc_endpoint.execute_api_endpoint.id
  subnet_id       = var.PUBLIC_SUBNET_1
}

resource "aws_vpc_endpoint_subnet_association" "execute_api_endpoint_association_2" {

  vpc_endpoint_id = aws_vpc_endpoint.execute_api_endpoint.id
  subnet_id       = var.PUBLIC_SUBNET_2
}

resource "aws_vpc_endpoint_subnet_association" "execute_api_endpoint_association_3" {

  vpc_endpoint_id = aws_vpc_endpoint.execute_api_endpoint.id
  subnet_id       = var.PUBLIC_SUBNET_3
}

resource "aws_vpc_endpoint" "s3" {

  vpc_id              = var.VPC_ID
  service_name        = "com.amazonaws.${var.AWS_REGION}.s3"
  route_table_ids     = var.SUBNET_IDS
  vpc_endpoint_type   = "Gateway"

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = var.USAGE
    Name = "s3-vpc-endpoint"
  }
}
