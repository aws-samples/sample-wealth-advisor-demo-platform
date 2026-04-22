// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

data "aws_ssm_parameter" "vpc_id" {

  name = "/${var.APP}/${var.ENV}/vpc_id"
}

data "aws_ssm_parameter" "vpc_private_subnet_ids" {

  name = "/${var.APP}/${var.ENV}/vpc_private_subnet_ids"
}

data "aws_vpc" "vpc" {
  id = data.aws_ssm_parameter.vpc_id.value
}

locals {
  PRIVATE_SUBNET1_ID = split(",", data.aws_ssm_parameter.vpc_private_subnet_ids.value)[0]
  PRIVATE_SUBNET2_ID = split(",", data.aws_ssm_parameter.vpc_private_subnet_ids.value)[1]
  PRIVATE_SUBNET3_ID = split(",", data.aws_ssm_parameter.vpc_private_subnet_ids.value)[2]
  VPC_ID                = data.aws_ssm_parameter.vpc_id.value
}

