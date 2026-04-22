// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

data "aws_ssm_parameter" "producer_role" {

  name = "/${var.APP}/${var.ENV}/sagemaker/producer/role"
}

data "aws_ssm_parameter" "consumer_role" {

  name = "/${var.APP}/${var.ENV}/sagemaker/consumer/role"
}

locals {
  PRODUCER_ROLE     = data.aws_ssm_parameter.producer_role.value
  CONSUMER_ROLE     = data.aws_ssm_parameter.consumer_role.value
}
