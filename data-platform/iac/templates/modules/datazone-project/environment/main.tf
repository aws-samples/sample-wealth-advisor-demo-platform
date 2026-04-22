// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

resource "awscc_datazone_environment_profile" "datalake_env_profile" {

  aws_account_id                   = var.account_id
  aws_account_region               = var.region
  domain_identifier                = var.domain_id
  environment_blueprint_identifier = var.environment_blueprint_id
  name                             = var.profile_name
  description                      = try(var.profile_description)
  project_identifier               = var.project_id
  #user_parameters                  = try(each.value.user_parameters)
}

# create datazone environment(s) in target project
resource "awscc_datazone_environment" "datalake_env" {

  domain_identifier              = var.domain_id
  environment_profile_identifier = awscc_datazone_environment_profile.datalake_env_profile.environment_profile_id
  name                           = var.env_name
  project_identifier             = var.project_id
}



