// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

resource "awscc_datazone_user_profile" "user_profile" {

  domain_identifier = data.aws_ssm_parameter.datazone_domain_id.value
  user_identifier   = var.user
}

resource "awscc_datazone_project_membership" "project_user" {

  domain_identifier     = data.aws_ssm_parameter.datazone_domain_id.value
  project_identifier    = data.aws_ssm_parameter.project_id.value
  designation           = var.designation

  member = {
    user_identifier     = var.user
  }
}



