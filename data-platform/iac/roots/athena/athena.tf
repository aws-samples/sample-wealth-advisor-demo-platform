// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

data "aws_kms_key" "athena_kms_key" {

  provider = aws.primary
  key_id   = "alias/${var.ATHENA_KMS_KEY_ALIAS}"
}

resource "aws_athena_workgroup" "athena_workgroup" {

  name = var.WORKGROUP_NAME

  configuration {

    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true

    result_configuration {

      output_location = var.ATHENA_OUTPUT_BUCKET

      encryption_configuration {

        encryption_option = "SSE_KMS"
        kms_key_arn       = data.aws_kms_key.athena_kms_key.arn
      }
    }
  }

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = "athena"
  }
}
