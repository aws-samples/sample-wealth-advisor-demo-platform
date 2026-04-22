// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

data "aws_iam_policy" "custom_user_policy" {

  name = "AmazonDataZoneRedshiftGlueProvisioningPolicy"
}

# Attache Policy
resource "aws_iam_role_policy_attachment" "custom_user_attach" {

  role       = data.aws_ssm_parameter.owner.value
  policy_arn = data.aws_iam_policy.custom_user_policy.arn
}

module "datazone_project_user" {

  source = "../../../templates/modules/datazone-project/user"

  APP             = var.APP
  ENV             = var.ENV
  project_name    = var.PROJECT_NAME
  designation     = var.DESIGNATION
  user            = data.aws_ssm_parameter.owner.value
}
