// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

output "tableName" {
  value       = aws_s3tables_table.iceberg.name
  description = "the name of the table"
}

output "namespace" {
  value       = aws_s3tables_table.iceberg.namespace
  description = "the namespace of the table"
}

output "tableArn" {
  value       = aws_s3tables_table.iceberg.arn
  description = "ARN of S3 table"
}
