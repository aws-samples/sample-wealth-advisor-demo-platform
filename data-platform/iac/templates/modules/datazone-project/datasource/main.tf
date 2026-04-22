// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

resource "awscc_datazone_data_source" "datasource" {

  domain_identifier       = var.domain_id
  name                    = var.datasource_name
  project_identifier      = var.project_id
  type                    = var.datasource_type
  configuration           = var.datasource_configuration
  environment_identifier  = var.environment_id
}

# add SSM parameter
resource "aws_ssm_parameter" "datasource_id" {

  name        = "/${var.APP}/${var.ENV}/${var.domain_id}/${var.datasource_name}/datasource_id"
  description = "The project id"
  type        = "SecureString"
  value       = awscc_datazone_data_source.datasource.id
  key_id      = var.KMS_KEY

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage       = var.USAGE
  }
  overwrite = true
}


