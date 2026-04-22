// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

data "aws_kms_key" "kms_key" {

  key_id   = "alias/${var.KMS_KEY_ALIAS}"
}

module "glue_scripts_bucket" {

  source = "../../../templates/modules/bucket"

  APP       = var.APP
  ENV       = var.ENV
  NAME      = "glue-scripts"
  USAGE     = "glue"  
  CMK_ARN   = data.aws_kms_key.kms_key.arn
}

module "glue_jars_bucket" {

  source = "../../../templates/modules/bucket"

  APP       = var.APP
  ENV       = var.ENV
  NAME      = "glue-jars"
  USAGE     = "glue"
  CMK_ARN   = data.aws_kms_key.kms_key.arn
}

module "glue_spark_logs_bucket" {

  source = "../../../templates/modules/bucket"

  APP       = var.APP
  ENV       = var.ENV
  NAME      = "glue-spark-logs"
  USAGE     = "glue"
  CMK_ARN   = data.aws_kms_key.kms_key.arn
}

module "glue_temp_bucket" {

  source = "../../../templates/modules/bucket"

  APP       = var.APP
  ENV       = var.ENV
  NAME      = "glue-temp"
  USAGE     = "glue"
  CMK_ARN   = data.aws_kms_key.kms_key.arn
}

module "athena_output_bucket" {

  source = "../../../templates/modules/bucket"
  
  APP       = var.APP
  ENV       = var.ENV
  NAME      = "athena-output"
  USAGE     = "athena"
  CMK_ARN   = data.aws_kms_key.kms_key.arn
}

locals {
  smus_projects_bucket_name = "${var.APP}-${var.ENV}-amazon-sagemaker-${local.account_id}"
}

module "smus_projects_bucket" {

  source = "../../../templates/modules/bucket"

  APP       = var.APP
  ENV       = var.ENV
  NAME      = "amazon-sagemaker"
  USAGE     = "smus_projects"
  CMK_ARN   = data.aws_kms_key.kms_key.arn
}

module "smus_cfn_bucket" {

  source = "../../../templates/modules/bucket"
  
  APP       = var.APP
  ENV       = var.ENV
  NAME      = "smus-project-cfn-template"
  USAGE     = "smus_projects"
  CMK_ARN   = data.aws_kms_key.kms_key.arn
}
