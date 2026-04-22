// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

output "table_bucket_arn" {
  value       = aws_s3tables_table_bucket.financial_advisor.arn
  description = "ARN of the S3 Tables bucket"
}

output "table_bucket_name" {
  value       = aws_s3tables_table_bucket.financial_advisor.name
  description = "Name of the S3 Tables bucket"
}

output "namespace" {
  value       = aws_s3tables_namespace.financial_advisor.namespace
  description = "Namespace for financial advisor tables"
}

output "table_arns" {
  value = {
    clients      = module.clients.tableArn
    advisors     = module.advisors.tableArn
    accounts     = module.accounts.tableArn
    portfolios   = module.portfolios.tableArn
    securities   = module.securities.tableArn
    transactions = module.transactions.tableArn
    holdings     = module.holdings.tableArn
    market_data  = module.market_data.tableArn
    performance  = module.performance.tableArn
    fees         = module.fees.tableArn
    goals        = module.goals.tableArn
    interactions = module.interactions.tableArn
    documents    = module.documents.tableArn
    compliance   = module.compliance.tableArn
    research     = module.research.tableArn
  }
  description = "ARNs of all financial advisor tables"
}
