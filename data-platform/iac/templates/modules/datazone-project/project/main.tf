// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

resource "awscc_datazone_project" "project" {

  domain_identifier   = var.domain_id
  name                = var.project_name
  description = try(var.project_description)
  #glossary_terms = try(var.glossary_terms)
}

/*
resource "awscc_datazone_project_membership" "project_owner" {

  domain_identifier = var.domain_id
  project_identifier = awscc_datazone_project.project.project_id
  member = {
    user_identifier = var.project_owner
  }
  designation = "PROJECT_OWNER"

}
*/

# Publish SSM parameter
resource "aws_ssm_parameter" "project_id" {

  name        = "/${var.APP}/${var.ENV}/${var.domain_id}/${var.project_name}/project_id"
  description = "The project id"
  type        = "SecureString"
  value       = awscc_datazone_project.project.project_id
  key_id      = var.KMS_KEY

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage       = var.USAGE
  }
  overwrite = true
}


