// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

# Example Usage:

# resource "aws_s3tables_table_bucket" "iceberg" {
#   name = "${var.appName}-${var.envName}-tableName"
# }

# resource "aws_s3tables_namespace" "iceberg" {
#   namespace        = "${var.appName}_${var.envName}_ns"
#   table_bucket_arn = aws_s3tables_table_bucket.iceberg.arn
# }

# module "s3-iceberg-table" {
#   source     = "./s3-table-iceberg"

#   TABLE_NAME  = "${var.appName}_${var.envName}_tableName"
#   NAMESPACE  = aws_s3tables_namespace.iceberg.namespace
#   BUCKET_ARN = aws_s3tables_table_bucket.iceberg.arn

#   FIELDS = [
#     {
#       name     = "example_id"
#       type     = "string"
#       required = true
#     },
#     {
#       name     = "example_name"
#       type     = "string"
#       required = true
#     }
#   ]

# }

resource "aws_s3tables_table" "iceberg" {
  
  name             = var.TABLE_NAME
  namespace        = var.NAMESPACE
  table_bucket_arn = var.BUCKET_ARN
  format           = "ICEBERG"

  metadata {
    iceberg {
      schema {
        dynamic "field" {
          for_each = var.FIELDS
          content {
            name = field.value.name
            type     = field.value.type
            required = field.value.required
          }
        }
      }
    }
  }

}


