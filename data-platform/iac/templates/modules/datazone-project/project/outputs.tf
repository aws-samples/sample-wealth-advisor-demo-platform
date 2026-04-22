// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

output "project_id" {
  value = awscc_datazone_project.project.project_id
  description = "DataZone projects"
}
