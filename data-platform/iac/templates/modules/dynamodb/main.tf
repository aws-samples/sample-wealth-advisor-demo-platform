locals {
  attributes = compact([var.hash_key, var.range_key])
}

data "aws_region" "current" {}

#
# Dynamo table
#
resource "aws_dynamodb_table" "table" {
  name             = var.table_name
  billing_mode     = "PAY_PER_REQUEST"
  hash_key         = var.hash_key
  range_key        = var.range_key
  stream_enabled   = var.stream_enabled
  stream_view_type = "NEW_AND_OLD_IMAGES"

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.dynamodb_kms_key_arn != null ? var.dynamodb_kms_key_arn : null
  }

  dynamic "attribute" {
    for_each = local.attributes
    iterator = attribute
    content {
      name = attribute.value
      type = "S"
    }
  }

  dynamic "attribute" {
    for_each = var.attributes
    iterator = attribute
    content {
      name = attribute.value["name"]
      type = attribute.value["type"]
    }
  }

  dynamic "local_secondary_index" {
    for_each = var.local_secondary_indices
    iterator = local_index
    content {
      name            = local_index.value["name"]
      range_key       = local_index.value["range_key"]
      projection_type = "ALL"
    }
  }

  dynamic "global_secondary_index" {
    for_each = var.global_secondary_indices
    iterator = global_index
    content {
      name            = global_index.value["name"]
      hash_key        = global_index.value["hash_key"]
      range_key       = global_index.value["range_key"]
      projection_type = "ALL"
    }
  }

  dynamic "import_table" {
    for_each = var.enable_import ? [1] : []
    content {
      input_format = var.import_format
      input_compression_type = var.import_compression_type

      s3_bucket_source {
        bucket = var.import_bucket_name
        key_prefix = var.import_key_prefix
      }

      input_format_options {
        csv {
          delimiter = var.csv_delimiter
          header_list = var.csv_header_list
        }
      }
    }
}
}