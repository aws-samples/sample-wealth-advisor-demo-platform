// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

data "aws_kms_key" "glue_kms_key" {
  key_id = "alias/${var.GLUE_KMS_KEY_ALIAS}"
}

data "aws_kms_key" "cloudwatch_kms_key" {
  key_id = "alias/${var.CLOUDWATCH_KMS_KEY_ALIAS}"
}

data "aws_iam_role" "glue_role" {
  name = var.GLUE_ROLE_NAME
}

resource "aws_glue_security_configuration" "glue_security_configuration" {
  name = "glue-security-configuration-financial-advisor"

  encryption_configuration {
    cloudwatch_encryption {
      cloudwatch_encryption_mode = "SSE-KMS"
      kms_key_arn                = data.aws_kms_key.cloudwatch_kms_key.arn
    }

    job_bookmarks_encryption {
      job_bookmarks_encryption_mode = "CSE-KMS"
      kms_key_arn                   = data.aws_kms_key.glue_kms_key.arn
    }

    s3_encryption {
      s3_encryption_mode = "SSE-KMS"
      kms_key_arn        = data.aws_kms_key.glue_kms_key.arn
    }
  }
}

data "aws_s3_bucket" "glue_scripts_bucket" {
  bucket = var.GLUE_SCRIPTS_BUCKET_NAME
}

resource "aws_s3_object" "glue_scripts" {
  for_each   = fileset("${path.module}/", "*.py")
  bucket     = data.aws_s3_bucket.glue_scripts_bucket.id
  key        = "financial-advisor/${each.value}"
  source     = "${path.module}/${each.value}"
  source_hash = filemd5("${path.module}/${each.value}")
  kms_key_id = data.aws_kms_key.glue_kms_key.arn
}

locals {
  tables = [
    "clients", "advisors", "accounts", "portfolios", "securities",
    "transactions", "holdings", "market_data", "performance", "fees",
    "goals", "interactions", "documents", "compliance", "research",
    "articles", "client_income_expense", "client_investment_restrictions",
    "client_reports", "crawl_log", "portfolio_config", "recommended_products",
    "theme_article_associations", "themes"
  ]
}

resource "aws_glue_job" "load_financial_advisor_data" {
  for_each = toset(local.tables)

  name              = "financial-advisor-load-${each.key}"
  role_arn          = data.aws_iam_role.glue_role.arn
  glue_version      = "5.0"
  worker_type       = "G.1X"
  number_of_workers = 2
  security_configuration = aws_glue_security_configuration.glue_security_configuration.name

  command {
    name            = "glueetl"
    script_location = "s3://${data.aws_s3_bucket.glue_scripts_bucket.id}/financial-advisor/load_data_to_s3table.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--enable-metrics"                   = "true"
    "--enable-spark-ui"                  = "true"
    "--enable-job-insights"              = "true"
    "--enable-glue-datacatalog"          = "true"
    "--enable-continuous-cloudwatch-log" = "true"
    "--job-bookmark-option"              = "job-bookmark-disable"
    "--datalake-formats"                 = "iceberg"
    "--extra-jars"                       = "s3://${var.AWS_ACCOUNT_ID}-${var.APP}-${var.ENV}-glue-jars/s3-tables-catalog-for-iceberg-runtime-0.1.7.jar"
    "--SOURCE_PATH"                      = "s3://${module.financial_advisor_data_bucket.bucket_id}/${each.key}.csv"
    "--TABLE_NAME"                       = each.key
    "--NAMESPACE"                        = "financial_advisor"
    "--TABLE_BUCKET_ARN"                 = aws_s3tables_table_bucket.financial_advisor.arn
  }

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage       = "financial-advisor-data-load"
  }

  depends_on = [aws_s3_object.glue_scripts]
}
