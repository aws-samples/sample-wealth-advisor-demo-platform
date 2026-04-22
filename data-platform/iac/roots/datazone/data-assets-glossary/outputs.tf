// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

output "glossary_id" {
  value       = aws_datazone_glossary.financial_advisor.id
  description = "Business glossary ID"
}

output "s3_tables_data_source_id" {
  value       = aws_datazone_data_source.s3_tables.id
  description = "S3 Tables data source ID"
}

output "redshift_data_source_id" {
  value       = aws_datazone_data_source.redshift_views.id
  description = "Redshift views data source ID"
}
