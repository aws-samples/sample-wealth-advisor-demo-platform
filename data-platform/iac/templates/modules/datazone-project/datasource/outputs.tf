// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

output "datasource_id" {
  value = awscc_datazone_data_source.datasource.data_source_id
  description = "DataZone projects"
}
