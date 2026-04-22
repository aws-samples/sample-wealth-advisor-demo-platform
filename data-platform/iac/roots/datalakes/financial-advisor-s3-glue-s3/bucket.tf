// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

data "aws_kms_key" "s3_kms_key" {
  key_id = "alias/${var.S3_KMS_KEY_ALIAS}"
}

module "financial_advisor_data_bucket" {
  source  = "../../../templates/modules/bucket"
  APP     = var.APP
  ENV     = var.ENV
  NAME    = "financial-advisor-s3-glue-s3-data"
  USAGE   = "financial-advisor"
  CMK_ARN = data.aws_kms_key.s3_kms_key.arn
}

resource "aws_s3_object" "financial_advisor_data_files" {
  for_each     = fileset("${path.module}/../../../../data/financial_advisor/", "*.csv")
  bucket       = module.financial_advisor_data_bucket.bucket_id
  key          = each.value
  source       = "${path.module}/../../../../data/financial_advisor/${each.value}"
  content_type = "text/csv"
  kms_key_id   = data.aws_kms_key.s3_kms_key.arn
  
  depends_on = [module.financial_advisor_data_bucket]
}
