// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

# Business Glossary for Financial Advisor Domain
resource "aws_datazone_glossary" "financial_advisor" {
  domain_identifier          = local.domain_id
  name                       = "Financial Advisor Glossary"
  description                = "Business glossary for financial advisor data analytics"
  owning_project_identifier  = local.producer_project_id
  status                     = "ENABLED"
}

# Glossary Terms - Financial Metrics
resource "aws_datazone_glossary_term" "aum" {
  domain_identifier   = local.domain_id
  glossary_identifier = aws_datazone_glossary.financial_advisor.id
  name                = "Assets Under Management"
  short_description   = "Total market value of assets managed by an advisor or for a client"
  long_description    = "AUM represents the total market value of all investment assets that a financial advisor manages on behalf of clients. This includes stocks, bonds, mutual funds, and other securities."
  status              = "ENABLED"
}

resource "aws_datazone_glossary_term" "twr" {
  domain_identifier   = local.domain_id
  glossary_identifier = aws_datazone_glossary.financial_advisor.id
  name                = "Time Weighted Return"
  short_description   = "Investment return metric that eliminates the effect of cash flows"
  long_description    = "TWR measures the compound rate of growth in a portfolio, removing the distorting effects of cash inflows and outflows. It's the standard for comparing portfolio performance."
  status              = "ENABLED"
}

resource "aws_datazone_glossary_term" "benchmark_return" {
  domain_identifier   = local.domain_id
  glossary_identifier = aws_datazone_glossary.financial_advisor.id
  name                = "Benchmark Return"
  short_description   = "Return of a market index used for performance comparison"
  long_description    = "The return of a standard market index (e.g., S&P 500) used to evaluate portfolio performance relative to the broader market."
  status              = "ENABLED"
}

resource "aws_datazone_glossary_term" "cost_basis" {
  domain_identifier   = local.domain_id
  glossary_identifier = aws_datazone_glossary.financial_advisor.id
  name                = "Cost Basis"
  short_description   = "Original purchase price of an investment"
  long_description    = "The original value or purchase price of an asset, used to calculate capital gains or losses for tax purposes."
  status              = "ENABLED"
}

# Glossary Terms - Client Attributes
resource "aws_datazone_glossary_term" "risk_tolerance" {
  domain_identifier   = local.domain_id
  glossary_identifier = aws_datazone_glossary.financial_advisor.id
  name                = "Risk Tolerance"
  short_description   = "Client's willingness to accept investment risk"
  long_description    = "A measure of how much market volatility and potential loss a client is willing to accept in pursuit of investment returns. Categories: Conservative, Moderate, Aggressive."
  status              = "ENABLED"
}

resource "aws_datazone_glossary_term" "investment_objectives" {
  domain_identifier   = local.domain_id
  glossary_identifier = aws_datazone_glossary.financial_advisor.id
  name                = "Investment Objectives"
  short_description   = "Client's financial goals and investment purpose"
  long_description    = "The primary financial goals a client aims to achieve through their investments, such as retirement, wealth accumulation, income generation, or capital preservation."
  status              = "ENABLED"
}

resource "aws_datazone_glossary_term" "client_segment" {
  domain_identifier   = local.domain_id
  glossary_identifier = aws_datazone_glossary.financial_advisor.id
  name                = "Client Segment"
  short_description   = "Classification of client based on wealth and service needs"
  long_description    = "Categorization of clients into segments (e.g., Mass Affluent, High Net Worth, Ultra High Net Worth) based on asset levels and service requirements."
  status              = "ENABLED"
}

resource "aws_datazone_glossary_term" "qualified_investor" {
  domain_identifier   = local.domain_id
  glossary_identifier = aws_datazone_glossary.financial_advisor.id
  name                = "Qualified Investor"
  short_description   = "Investor meeting regulatory criteria for certain investments"
  long_description    = "An investor who meets specific income or net worth thresholds, allowing access to certain investment products not available to retail investors."
  status              = "ENABLED"
}

# Glossary Terms - Compliance
resource "aws_datazone_glossary_term" "kyc" {
  domain_identifier   = local.domain_id
  glossary_identifier = aws_datazone_glossary.financial_advisor.id
  name                = "Know Your Customer"
  short_description   = "Process of verifying client identity and assessing risk"
  long_description    = "KYC is a regulatory requirement to verify the identity of clients and assess their suitability for financial services, helping prevent fraud and money laundering."
  status              = "ENABLED"
}

resource "aws_datazone_glossary_term" "aml" {
  domain_identifier   = local.domain_id
  glossary_identifier = aws_datazone_glossary.financial_advisor.id
  name                = "Anti-Money Laundering"
  short_description   = "Compliance checks to prevent financial crimes"
  long_description    = "AML refers to regulations and procedures designed to prevent criminals from disguising illegally obtained funds as legitimate income."
  status              = "ENABLED"
}

resource "aws_datazone_glossary_term" "suitability" {
  domain_identifier   = local.domain_id
  glossary_identifier = aws_datazone_glossary.financial_advisor.id
  name                = "Suitability"
  short_description   = "Assessment that investments match client profile"
  long_description    = "Suitability analysis ensures that investment recommendations align with a client's financial situation, risk tolerance, and investment objectives."
  status              = "ENABLED"
}

# Glossary Terms - Portfolio Management
resource "aws_datazone_glossary_term" "target_allocation" {
  domain_identifier   = local.domain_id
  glossary_identifier = aws_datazone_glossary.financial_advisor.id
  name                = "Target Allocation"
  short_description   = "Desired distribution of assets across investment types"
  long_description    = "The strategic mix of asset classes (stocks, bonds, cash, etc.) that a portfolio aims to maintain based on the client's goals and risk tolerance."
  status              = "ENABLED"
}

resource "aws_datazone_glossary_term" "unrealized_gain_loss" {
  domain_identifier   = local.domain_id
  glossary_identifier = aws_datazone_glossary.financial_advisor.id
  name                = "Unrealized Gain/Loss"
  short_description   = "Profit or loss on holdings not yet sold"
  long_description    = "The difference between the current market value and cost basis of a security that is still held (not sold). Becomes realized when the position is closed."
  status              = "ENABLED"
}
