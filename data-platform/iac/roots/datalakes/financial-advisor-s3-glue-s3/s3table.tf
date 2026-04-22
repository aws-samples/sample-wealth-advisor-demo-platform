// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

data "aws_kms_key" "s3tables_kms_key" {
  key_id = "alias/${var.S3_TABLES_KMS_KEY_ALIAS}"
}

resource "aws_s3tables_table_bucket" "financial_advisor" {
  name = "financial-advisor-s3table"

  encryption_configuration = {
    sse_algorithm = "aws:kms"
    kms_key_arn   = data.aws_kms_key.s3tables_kms_key.arn
  }
}

resource "aws_s3tables_namespace" "financial_advisor" {
  namespace        = "financial_advisor"
  table_bucket_arn = aws_s3tables_table_bucket.financial_advisor.arn
}

module "clients" {
  source     = "../../../templates/modules/s3-table-iceberg"
  BUCKET_ARN = aws_s3tables_table_bucket.financial_advisor.arn
  NAMESPACE  = aws_s3tables_namespace.financial_advisor.namespace
  TABLE_NAME = "clients"
  FIELDS = [
    { name = "client_id", type = "string", required = true },
    { name = "first_name", type = "string", required = true },
    { name = "last_name", type = "string", required = true },
    { name = "email", type = "string", required = true },
    { name = "phone", type = "string", required = false },
    { name = "address", type = "string", required = false },
    { name = "city", type = "string", required = false },
    { name = "state", type = "string", required = false },
    { name = "zip", type = "string", required = false },
    { name = "date_of_birth", type = "date", required = false },
    { name = "risk_tolerance", type = "string", required = false },
    { name = "investment_objectives", type = "string", required = false },
    { name = "segment", type = "string", required = false },
    { name = "status", type = "string", required = false },
    { name = "advisor_id", type = "string", required = false },
    { name = "created_date", type = "date", required = false },
    { name = "sophistication", type = "string", required = false },
    { name = "qualified_investor", type = "boolean", required = false },
    { name = "service_model", type = "string", required = false }
  ]
}

module "advisors" {
  source     = "../../../templates/modules/s3-table-iceberg"
  BUCKET_ARN = aws_s3tables_table_bucket.financial_advisor.arn
  NAMESPACE  = aws_s3tables_namespace.financial_advisor.namespace
  TABLE_NAME = "advisors"
  FIELDS = [
    { name = "advisor_id", type = "string", required = true },
    { name = "first_name", type = "string", required = true },
    { name = "last_name", type = "string", required = true },
    { name = "email", type = "string", required = true },
    { name = "phone", type = "string", required = false },
    { name = "title", type = "string", required = false },
    { name = "credentials", type = "string", required = false },
    { name = "specialization", type = "string", required = false },
    { name = "years_experience", type = "int", required = false },
    { name = "hire_date", type = "date", required = false }
  ]
}

module "accounts" {
  source     = "../../../templates/modules/s3-table-iceberg"
  BUCKET_ARN = aws_s3tables_table_bucket.financial_advisor.arn
  NAMESPACE  = aws_s3tables_namespace.financial_advisor.namespace
  TABLE_NAME = "accounts"
  FIELDS = [
    { name = "account_id", type = "string", required = true },
    { name = "client_id", type = "string", required = true },
    { name = "account_type", type = "string", required = false },
    { name = "account_name", type = "string", required = false },
    { name = "opening_date", type = "date", required = false },
    { name = "investment_strategy", type = "string", required = false },
    { name = "status", type = "string", required = false },
    { name = "current_balance", type = "decimal(18,2)", required = false }
  ]
}

module "portfolios" {
  source     = "../../../templates/modules/s3-table-iceberg"
  BUCKET_ARN = aws_s3tables_table_bucket.financial_advisor.arn
  NAMESPACE  = aws_s3tables_namespace.financial_advisor.namespace
  TABLE_NAME = "portfolios"
  FIELDS = [
    { name = "portfolio_id", type = "string", required = true },
    { name = "account_id", type = "string", required = true },
    { name = "portfolio_name", type = "string", required = false },
    { name = "investment_model", type = "string", required = false },
    { name = "target_allocation", type = "string", required = false },
    { name = "benchmark", type = "string", required = false },
    { name = "inception_date", type = "date", required = false }
  ]
}

module "securities" {
  source     = "../../../templates/modules/s3-table-iceberg"
  BUCKET_ARN = aws_s3tables_table_bucket.financial_advisor.arn
  NAMESPACE  = aws_s3tables_namespace.financial_advisor.namespace
  TABLE_NAME = "securities"
  FIELDS = [
    { name = "security_id", type = "string", required = true },
    { name = "ticker", type = "string", required = false },
    { name = "security_name", type = "string", required = false },
    { name = "security_type", type = "string", required = false },
    { name = "asset_class", type = "string", required = false },
    { name = "sector", type = "string", required = false },
    { name = "current_price", type = "decimal(18,2)", required = false },
    { name = "price_date", type = "date", required = false }
  ]
}

module "transactions" {
  source     = "../../../templates/modules/s3-table-iceberg"
  BUCKET_ARN = aws_s3tables_table_bucket.financial_advisor.arn
  NAMESPACE  = aws_s3tables_namespace.financial_advisor.namespace
  TABLE_NAME = "transactions"
  FIELDS = [
    { name = "transaction_id", type = "string", required = true },
    { name = "account_id", type = "string", required = true },
    { name = "security_id", type = "string", required = false },
    { name = "transaction_type", type = "string", required = false },
    { name = "transaction_date", type = "date", required = false },
    { name = "settlement_date", type = "date", required = false },
    { name = "quantity", type = "decimal(18,4)", required = false },
    { name = "price", type = "decimal(18,2)", required = false },
    { name = "amount", type = "decimal(18,2)", required = false },
    { name = "status", type = "string", required = false }
  ]
}

module "holdings" {
  source     = "../../../templates/modules/s3-table-iceberg"
  BUCKET_ARN = aws_s3tables_table_bucket.financial_advisor.arn
  NAMESPACE  = aws_s3tables_namespace.financial_advisor.namespace
  TABLE_NAME = "holdings"
  FIELDS = [
    { name = "position_id", type = "string", required = true },
    { name = "portfolio_id", type = "string", required = true },
    { name = "security_id", type = "string", required = false },
    { name = "quantity", type = "decimal(18,4)", required = false },
    { name = "cost_basis", type = "decimal(18,2)", required = false },
    { name = "current_price", type = "decimal(18,2)", required = false },
    { name = "market_value", type = "decimal(18,2)", required = false },
    { name = "unrealized_gain_loss", type = "decimal(18,2)", required = false },
    { name = "as_of_date", type = "date", required = false }
  ]
}

module "market_data" {
  source     = "../../../templates/modules/s3-table-iceberg"
  BUCKET_ARN = aws_s3tables_table_bucket.financial_advisor.arn
  NAMESPACE  = aws_s3tables_namespace.financial_advisor.namespace
  TABLE_NAME = "market_data"
  FIELDS = [
    { name = "market_data_id", type = "string", required = true },
    { name = "security_id", type = "string", required = true },
    { name = "price_date", type = "date", required = false },
    { name = "open_price", type = "decimal(18,2)", required = false },
    { name = "high_price", type = "decimal(18,2)", required = false },
    { name = "low_price", type = "decimal(18,2)", required = false },
    { name = "close_price", type = "decimal(18,2)", required = false },
    { name = "volume", type = "long", required = false }
  ]
}

module "performance" {
  source     = "../../../templates/modules/s3-table-iceberg"
  BUCKET_ARN = aws_s3tables_table_bucket.financial_advisor.arn
  NAMESPACE  = aws_s3tables_namespace.financial_advisor.namespace
  TABLE_NAME = "performance"
  FIELDS = [
    { name = "performance_id", type = "string", required = true },
    { name = "portfolio_id", type = "string", required = true },
    { name = "period", type = "string", required = false },
    { name = "period_start_date", type = "date", required = false },
    { name = "period_end_date", type = "date", required = false },
    { name = "time_weighted_return", type = "decimal(18,6)", required = false },
    { name = "benchmark_return", type = "decimal(18,6)", required = false },
    { name = "beginning_value", type = "decimal(18,2)", required = false },
    { name = "ending_value", type = "decimal(18,2)", required = false }
  ]
}

module "fees" {
  source     = "../../../templates/modules/s3-table-iceberg"
  BUCKET_ARN = aws_s3tables_table_bucket.financial_advisor.arn
  NAMESPACE  = aws_s3tables_namespace.financial_advisor.namespace
  TABLE_NAME = "fees"
  FIELDS = [
    { name = "fee_id", type = "string", required = true },
    { name = "account_id", type = "string", required = true },
    { name = "fee_type", type = "string", required = false },
    { name = "fee_rate", type = "decimal(18,6)", required = false },
    { name = "billing_date", type = "date", required = false },
    { name = "fee_amount", type = "decimal(18,2)", required = false },
    { name = "payment_status", type = "string", required = false },
    { name = "payment_date", type = "date", required = false }
  ]
}

module "goals" {
  source     = "../../../templates/modules/s3-table-iceberg"
  BUCKET_ARN = aws_s3tables_table_bucket.financial_advisor.arn
  NAMESPACE  = aws_s3tables_namespace.financial_advisor.namespace
  TABLE_NAME = "goals"
  FIELDS = [
    { name = "goal_id", type = "string", required = true },
    { name = "client_id", type = "string", required = true },
    { name = "goal_type", type = "string", required = false },
    { name = "goal_name", type = "string", required = false },
    { name = "target_amount", type = "decimal(18,2)", required = false },
    { name = "current_value", type = "decimal(18,2)", required = false },
    { name = "target_date", type = "date", required = false },
    { name = "funding_status", type = "string", required = false },
    { name = "probability_of_success", type = "int", required = false },
    { name = "created_date", type = "date", required = false }
  ]
}

module "interactions" {
  source     = "../../../templates/modules/s3-table-iceberg"
  BUCKET_ARN = aws_s3tables_table_bucket.financial_advisor.arn
  NAMESPACE  = aws_s3tables_namespace.financial_advisor.namespace
  TABLE_NAME = "interactions"
  FIELDS = [
    { name = "interaction_id", type = "string", required = true },
    { name = "client_id", type = "string", required = true },
    { name = "advisor_id", type = "string", required = false },
    { name = "interaction_type", type = "string", required = false },
    { name = "interaction_date", type = "date", required = false },
    { name = "subject", type = "string", required = false },
    { name = "summary", type = "string", required = false },
    { name = "sentiment", type = "string", required = false },
    { name = "duration_minutes", type = "int", required = false }
  ]
}

module "documents" {
  source     = "../../../templates/modules/s3-table-iceberg"
  BUCKET_ARN = aws_s3tables_table_bucket.financial_advisor.arn
  NAMESPACE  = aws_s3tables_namespace.financial_advisor.namespace
  TABLE_NAME = "documents"
  FIELDS = [
    { name = "document_id", type = "string", required = true },
    { name = "client_id", type = "string", required = true },
    { name = "account_id", type = "string", required = false },
    { name = "document_type", type = "string", required = false },
    { name = "document_name", type = "string", required = false },
    { name = "upload_date", type = "date", required = false },
    { name = "file_size_kb", type = "int", required = false },
    { name = "storage_location", type = "string", required = false }
  ]
}

module "compliance" {
  source     = "../../../templates/modules/s3-table-iceberg"
  BUCKET_ARN = aws_s3tables_table_bucket.financial_advisor.arn
  NAMESPACE  = aws_s3tables_namespace.financial_advisor.namespace
  TABLE_NAME = "compliance"
  FIELDS = [
    { name = "compliance_id", type = "string", required = true },
    { name = "client_id", type = "string", required = true },
    { name = "kyc_status", type = "string", required = false },
    { name = "kyc_date", type = "date", required = false },
    { name = "aml_status", type = "string", required = false },
    { name = "aml_date", type = "date", required = false },
    { name = "suitability_status", type = "string", required = false },
    { name = "suitability_date", type = "date", required = false },
    { name = "next_review_date", type = "date", required = false }
  ]
}

module "research" {
  source     = "../../../templates/modules/s3-table-iceberg"
  BUCKET_ARN = aws_s3tables_table_bucket.financial_advisor.arn
  NAMESPACE  = aws_s3tables_namespace.financial_advisor.namespace
  TABLE_NAME = "research"
  FIELDS = [
    { name = "research_id", type = "string", required = true },
    { name = "security_id", type = "string", required = true },
    { name = "research_type", type = "string", required = false },
    { name = "publication_date", type = "date", required = false },
    { name = "rating", type = "string", required = false },
    { name = "target_price", type = "decimal(18,2)", required = false },
    { name = "analyst_name", type = "string", required = false },
    { name = "analyst_firm", type = "string", required = false },
    { name = "summary", type = "string", required = false }
  ]
}

module "articles" {
  source     = "../../../templates/modules/s3-table-iceberg"
  BUCKET_ARN = aws_s3tables_table_bucket.financial_advisor.arn
  NAMESPACE  = aws_s3tables_namespace.financial_advisor.namespace
  TABLE_NAME = "articles"
  FIELDS = [
    { name = "content_hash", type = "string", required = true },
    { name = "url", type = "string", required = true },
    { name = "title", type = "string", required = false },
    { name = "content", type = "string", required = false },
    { name = "summary", type = "string", required = false },
    { name = "published_date", type = "timestamp", required = false },
    { name = "source", type = "string", required = false },
    { name = "author", type = "string", required = false },
    { name = "file_path", type = "string", required = false },
    { name = "created_at", type = "timestamp", required = false }
  ]
}

module "client_income_expense" {
  source     = "../../../templates/modules/s3-table-iceberg"
  BUCKET_ARN = aws_s3tables_table_bucket.financial_advisor.arn
  NAMESPACE  = aws_s3tables_namespace.financial_advisor.namespace
  TABLE_NAME = "client_income_expense"
  FIELDS = [
    { name = "client_id", type = "string", required = true },
    { name = "as_of_date", type = "date", required = true },
    { name = "monthly_income", type = "decimal(18,2)", required = true },
    { name = "monthly_expenses", type = "decimal(18,2)", required = true },
    { name = "sustainability_years", type = "decimal(10,2)", required = true }
  ]
}

module "client_investment_restrictions" {
  source     = "../../../templates/modules/s3-table-iceberg"
  BUCKET_ARN = aws_s3tables_table_bucket.financial_advisor.arn
  NAMESPACE  = aws_s3tables_namespace.financial_advisor.namespace
  TABLE_NAME = "client_investment_restrictions"
  FIELDS = [
    { name = "restriction_id", type = "string", required = true },
    { name = "client_id", type = "string", required = true },
    { name = "restriction", type = "string", required = true },
    { name = "created_date", type = "date", required = false }
  ]
}

module "client_reports" {
  source     = "../../../templates/modules/s3-table-iceberg"
  BUCKET_ARN = aws_s3tables_table_bucket.financial_advisor.arn
  NAMESPACE  = aws_s3tables_namespace.financial_advisor.namespace
  TABLE_NAME = "client_reports"
  FIELDS = [
    { name = "report_id", type = "string", required = true },
    { name = "client_id", type = "string", required = true },
    { name = "generated_date", type = "timestamp", required = true },
    { name = "download_date", type = "timestamp", required = false },
    { name = "status", type = "string", required = true },
    { name = "s3_path", type = "string", required = false },
    { name = "next_best_action", type = "string", required = false }
  ]
}

module "crawl_log" {
  source     = "../../../templates/modules/s3-table-iceberg"
  BUCKET_ARN = aws_s3tables_table_bucket.financial_advisor.arn
  NAMESPACE  = aws_s3tables_namespace.financial_advisor.namespace
  TABLE_NAME = "crawl_log"
  FIELDS = [
    { name = "log_id", type = "long", required = true },
    { name = "timestamp", type = "timestamp", required = true },
    { name = "total_crawled", type = "int", required = false },
    { name = "new_articles", type = "int", required = false },
    { name = "duplicates", type = "int", required = false },
    { name = "errors", type = "int", required = false },
    { name = "sources_stats", type = "string", required = false },
    { name = "created_at", type = "timestamp", required = false }
  ]
}

module "portfolio_config" {
  source     = "../../../templates/modules/s3-table-iceberg"
  BUCKET_ARN = aws_s3tables_table_bucket.financial_advisor.arn
  NAMESPACE  = aws_s3tables_namespace.financial_advisor.namespace
  TABLE_NAME = "portfolio_config"
  FIELDS = [
    { name = "client_id", type = "string", required = true },
    { name = "tickers", type = "string", required = false },
    { name = "generated_at", type = "timestamp", required = false },
    { name = "created_at", type = "timestamp", required = false },
    { name = "updated_at", type = "timestamp", required = false }
  ]
}

module "recommended_products" {
  source     = "../../../templates/modules/s3-table-iceberg"
  BUCKET_ARN = aws_s3tables_table_bucket.financial_advisor.arn
  NAMESPACE  = aws_s3tables_namespace.financial_advisor.namespace
  TABLE_NAME = "recommended_products"
  FIELDS = [
    { name = "product_id", type = "string", required = true },
    { name = "product_name", type = "string", required = true },
    { name = "product_type", type = "string", required = true },
    { name = "description", type = "string", required = false },
    { name = "status", type = "string", required = true },
    { name = "created_date", type = "date", required = false }
  ]
}

module "theme_article_associations" {
  source     = "../../../templates/modules/s3-table-iceberg"
  BUCKET_ARN = aws_s3tables_table_bucket.financial_advisor.arn
  NAMESPACE  = aws_s3tables_namespace.financial_advisor.namespace
  TABLE_NAME = "theme_article_associations"
  FIELDS = [
    { name = "theme_id", type = "string", required = true },
    { name = "article_hash", type = "string", required = true },
    { name = "client_id", type = "string", required = true },
    { name = "created_at", type = "timestamp", required = false }
  ]
}

module "themes" {
  source     = "../../../templates/modules/s3-table-iceberg"
  BUCKET_ARN = aws_s3tables_table_bucket.financial_advisor.arn
  NAMESPACE  = aws_s3tables_namespace.financial_advisor.namespace
  TABLE_NAME = "themes"
  FIELDS = [
    { name = "theme_id", type = "string", required = true },
    { name = "client_id", type = "string", required = true },
    { name = "title", type = "string", required = true },
    { name = "sentiment", type = "string", required = false },
    { name = "article_count", type = "int", required = false },
    { name = "sources", type = "string", required = false },
    { name = "created_at", type = "timestamp", required = false },
    { name = "summary", type = "string", required = false },
    { name = "updated_at", type = "timestamp", required = false },
    { name = "score", type = "decimal(10,2)", required = false },
    { name = "rank", type = "int", required = false },
    { name = "score_breakdown", type = "string", required = false },
    { name = "generated_at", type = "timestamp", required = false },
    { name = "relevance_score", type = "decimal(10,2)", required = false },
    { name = "combined_score", type = "decimal(10,2)", required = false },
    { name = "matched_tickers", type = "string", required = false },
    { name = "relevance_reasoning", type = "string", required = false },
    { name = "ticker", type = "string", required = false }
  ]
}

data "aws_iam_policy_document" "financial_advisor_bucket_policy_document" {
  statement {
    sid    = "AllowAthenaAccess"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["athena.amazonaws.com"]
    }
    actions = ["s3tables:*"]
    resources = [
      "${aws_s3tables_table_bucket.financial_advisor.arn}/*",
      aws_s3tables_table_bucket.financial_advisor.arn
    ]
  }

  statement {
    sid    = "AllowGlueAccess"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }
    actions = ["s3tables:*"]
    resources = [
      "${aws_s3tables_table_bucket.financial_advisor.arn}/*",
      aws_s3tables_table_bucket.financial_advisor.arn
    ]
  }
}

resource "aws_s3tables_table_bucket_policy" "financial_advisor_policy" {
  resource_policy  = data.aws_iam_policy_document.financial_advisor_bucket_policy_document.json
  table_bucket_arn = aws_s3tables_table_bucket.financial_advisor.arn
}
