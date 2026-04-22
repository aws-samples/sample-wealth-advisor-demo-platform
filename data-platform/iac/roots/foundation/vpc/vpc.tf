// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

locals {
  min_az_count_required = 3
  max_az_count     = min(3, length(data.aws_availability_zones.available.zone_ids))
}

# VPC
resource "aws_vpc" "main" {

  cidr_block           = "10.38.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name                                     = "${var.APP}-${var.ENV}-vpc"
    Application                              = var.APP
    Environment                              = var.ENV
  }

  # Before creating the VPC, first check if it supports the minimum # of required availability zones
  lifecycle {
    precondition {
      condition     = length(data.aws_availability_zones.available.zone_ids) >= local.min_az_count_required
      error_message = "Region must have at least ${local.min_az_count_required} availability zones."
    }
  }
}

# Save the VPC Id in SSM Parameter Store
resource "aws_ssm_parameter" "vpc_id" {
  name      = "/${var.APP}/${var.ENV}/vpc_id"
  type      = "SecureString"
  value     = aws_vpc.main.id
  key_id    = data.aws_kms_key.ssm_kms_key.key_id
  overwrite = true

  tags = {
    Application = var.APP
    Environment = var.ENV
  }
}
