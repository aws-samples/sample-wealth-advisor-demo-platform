// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

# Get domain and project IDs from SSM
data "aws_ssm_parameter" "domain_id" {
  name = "/${var.APP}/${var.ENV}/sagemaker/domain/id"
}

data "aws_ssm_parameter" "producer_project_id" {
  name = "/${var.APP}/${var.ENV}/sagemaker/producer/project-id"
}

data "aws_ssm_parameter" "consumer_project_id" {
  name = "/${var.APP}/${var.ENV}/sagemaker/consumer/project-id"
}

locals {
  domain_id           = coalesce(var.DOMAIN_ID, data.aws_ssm_parameter.domain_id.value)
  producer_project_id = coalesce(var.PRODUCER_PROJECT_ID, data.aws_ssm_parameter.producer_project_id.value)
  consumer_project_id = coalesce(var.CONSUMER_PROJECT_ID, data.aws_ssm_parameter.consumer_project_id.value)
}
