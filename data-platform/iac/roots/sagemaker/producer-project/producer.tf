// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

data "aws_kms_key" "s3_primary_key" {

  provider = aws.primary

  key_id   = "alias/${var.S3_PRIMARY_KMS_KEY_ALIAS}"
}

data "aws_kms_key" "s3_secondary_key" {

  provider = aws.secondary

  key_id   = "alias/${var.S3_SECONDARY_KMS_KEY_ALIAS}"
}

# Create Sagemaker Project for Producer
module "producer_project" {

  source = "../../../templates/modules/sagemaker-project"

  S3BUCKET                      = "${var.S3BUCKET}"
  PROJECT_NAME                  = var.PRODUCER_PROJECT_NAME
  PROJECT_DESCRIPTION           = var.PRODUCER_PROJECT_DESCRIPTION
  GLUE_DB                       = var.GLUE_DB_NAME
  APP                           = var.APP
  ENV                           = var.ENV
  SSM_KMS_KEY_ALIAS             = var.SSM_KMS_KEY_ALIAS


}

