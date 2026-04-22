// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

output "glue_role" {
  value = aws_iam_role.glue.arn
  description = "DataZone projects"
}

output "provision_role" {
  value = aws_iam_role.datazone_provisioning.arn
  description = "DataZone projects"
}

output "environment_role" {
  value = aws_iam_role.environment_role.arn
  description = "DataZone projects"
}


output "glue_profile_id" {
  value = aws_datazone_environment_blueprint_configuration.dz_datalake.environment_blueprint_id
  description = "DataZone projects"
}

output "custom_profile_id" {
  value = awscc_datazone_environment_blueprint_configuration.dz_custom.environment_blueprint_id
  description = "DataZone projects"
}
