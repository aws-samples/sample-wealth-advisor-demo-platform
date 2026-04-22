// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

output "environment_id" {
  value = awscc_datazone_environment.datalake_env.environment_id
  description = "DataZone projects"
}
