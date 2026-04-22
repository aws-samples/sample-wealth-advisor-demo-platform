// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

resource "awscc_datazone_environment_profile" "custom_env_profile" {

  aws_account_id                   = var.account_id
  aws_account_region               = var.region
  domain_identifier                = var.domain_id
  environment_blueprint_identifier = var.environment_blueprint_id
  name                             = var.env_name
  description                      = try(var.description)
  project_identifier               = var.project_id
  #user_parameters                  = try(each.value.user_parameters)
}

# create environment using custom blueprint
resource "awscc_datazone_environment" "custom_env" {

  domain_identifier              = var.domain_id
  environment_profile_identifier = awscc_datazone_environment_profile.custom_env_profile.environment_profile_id
  name                           = var.env_name
  project_identifier             = var.project_id
  description                    = var.description
  environment_account_identifier         = var.account_id
  environment_account_region             = var.region

}

# associate environment role to environment
resource "null_resource" "associateRoletoEnv" {

  provisioner "local-exec" {
    command = <<-EOT
      aws datazone associate-environment-role \
        --domain-identifier "${var.domain_id}" \
        --environment-identifier "${awscc_datazone_environment.custom_env.environment_id}" \
        --environment-role-arn "${var.environment_role}" 
    EOT
  }

}

# Add existing resources to environment
resource "awscc_datazone_environment_actions" "env_action" {
  for_each = var.env_actions
  name                           = each.key
  environment_identifier = awscc_datazone_environment.custom_env.environment_id
  description = each.value.description
  domain_identifier = var.domain_id
  parameters = {
    uri = each.value.link
  }
}












