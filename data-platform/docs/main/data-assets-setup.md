# Data Assets and Business Glossary Setup

This guide explains how to create data assets, metadata, and business glossaries for S3 Tables and Redshift views in SageMaker Unified Studio.

## Overview

Since DataZone requires domain authentication (not just IAM), all setup is done through the **SageMaker Studio UI**. CSV files are provided for easy import.

## Prerequisites

1. SageMaker domain deployed
2. Producer and consumer projects created
3. S3 Tables deployed with data loaded
4. Redshift views created

## Setup Steps

### Step 1: Create Business Glossary

1. Open **SageMaker Studio** → **Producer Project**
2. Navigate to **Governance** → **Business glossary** (left sidebar)
3. Click **Create glossary**
4. Fill in:
   - Name: `Financial Advisor Glossary`
   - Description: `Business glossary for financial advisor data analytics`
5. Click **Create**

### Step 2: Import Glossary Terms

1. Click on the glossary you just created
2. Click **Import terms**
3. Upload: `glossary/business_glossary_terms.csv`
4. Map columns:
   - Name → name
   - Short description → short_description
   - Long description → long_description
5. Click **Import**

**12 terms imported:**
- Assets Under Management
- Time Weighted Return
- Benchmark Return
- Cost Basis
- Risk Tolerance
- Investment Objectives
- Qualified Investor
- Know Your Customer
- Anti Money Laundering
- Suitability
- Target Allocation
- Unrealized Gain Loss

### Step 3: Create S3 Tables Data Source

1. In **Producer Project**, go to **Data** → **Data sources**
2. Click **Create data source**
3. Select **AWS Glue**
4. Configure:
   - Name: `Financial Advisor S3 Tables`
   - Description: `S3 Tables with financial advisor data in Iceberg format`
   - Glue catalog: `s3tablescatalog`
   - Database: `financial_advisor`
   - Data access role: Select the producer project role
   - Publish on import: **Enabled**
   - Schedule: Daily at midnight (optional)
5. Click **Create**

### Step 4: Create Redshift Data Source

1. In **Producer Project**, go to **Data** → **Data sources**
2. Click **Create data source**
3. Select **Amazon Redshift**
4. Configure:
   - Name: `Financial Advisor Redshift Views`
   - Description: `Redshift views for financial advisor analytics`
   - Connection type: **Redshift Serverless**
   - Workgroup: Select your producer project workgroup
   - Database: `dev`
   - Schema: `public`
   - Authentication: Create new secret or select existing
     - Username: `admin`
     - Password: Your Redshift admin password
   - Publish on import: **Enabled**
   - Schedule: Daily at 1 AM (optional)
5. Click **Create**

### Step 5: Run Data Source Discovery

**For S3 Tables:**
1. Go to **Data sources**
2. Select `Financial Advisor S3 Tables`
3. Click **Run**
4. Wait 5-10 minutes for discovery to complete
5. Check **Data** → **Assets** to see 24 imported tables

**For Redshift Views:**
1. Go to **Data sources**
2. Select `Financial Advisor Redshift Views`
3. Click **Run**
4. Wait 5-10 minutes for discovery to complete
5. Check **Data** → **Assets** to see 5 imported views

### Step 6: Add Metadata to Assets

Use the CSV files as reference to add metadata:

**For each S3 Table:**
1. Go to **Data** → **Assets**
2. Click on a table (e.g., `clients`)
3. Click **Edit**
4. Add from `glossary/table_metadata.csv`:
   - Business name
   - Description
   - Tags
   - Data classification
5. Go to **Schema** tab
6. Add glossary terms to relevant columns:
   - `risk_tolerance` → Link to "Risk Tolerance" term
   - `investment_objectives` → Link to "Investment Objectives" term
   - etc.
7. Click **Save**

**For each Redshift View:**
1. Follow same process using `glossary/view_metadata.csv`

### Step 7: Publish Assets to Catalog

1. Select assets to publish
2. Click **Publish**
3. Add publishing notes
4. Click **Publish to catalog**

### Step 8: Subscribe from Consumer Project (Optional)

1. Open **Consumer Project**
2. Go to **Data catalog**
3. Search for published assets
4. Click **Subscribe**
5. Wait for producer approval
6. Query the data

## Files Created

- `glossary/business_glossary_terms.csv` - 12 glossary terms for import
- `glossary/table_metadata.csv` - Metadata for 24 S3 Tables
- `glossary/view_metadata.csv` - Metadata for 5 Redshift views

## Quick Reference

### Glossary Terms to Column Mapping

**clients table:**
- `risk_tolerance` → Risk Tolerance
- `investment_objectives` → Investment Objectives
- `qualified_investor` → Qualified Investor

**performance table:**
- `time_weighted_return` → Time Weighted Return
- `benchmark_return` → Benchmark Return

**holdings table:**
- `cost_basis` → Cost Basis
- `unrealized_gain_loss` → Unrealized Gain Loss

**compliance table:**
- `kyc_status` → Know Your Customer
- `aml_status` → Anti Money Laundering
- `suitability_status` → Suitability

**portfolios table:**
- `target_allocation` → Target Allocation

**accounts/performance tables:**
- `current_balance`, `ending_value` → Assets Under Management

## Why CLI Doesn't Work

DataZone uses **domain-based authentication** through IAM Identity Center, not direct IAM credentials. Even with Admin IAM permissions, you need to:
- Be a member of the domain (via IAM Identity Center)
- Have appropriate project roles (Owner, Contributor)
- Authenticate through the SageMaker Studio portal

The UI automatically handles this authentication, which is why it's the recommended approach.

## Troubleshooting

**Can't see glossary:**
- Glossaries are domain-level, visible from domain → Governance
- Also accessible when editing assets in any project

**Data source discovery fails:**
- Verify Lake Formation permissions
- Check IAM role has Glue/Redshift access
- Ensure catalog/database exists

**Can't publish assets:**
- Must be project Owner or have publish permissions
- Assets must be in ACTIVE state
- Metadata must be complete

**CSV import fails:**
- Ensure CSV has correct headers
- Check for special characters in descriptions
- Verify file encoding is UTF-8

## Next Steps

After setup:
1. Enrich column-level metadata
2. Create data quality rules
3. Set up lineage tracking
4. Configure subscription workflows
5. Train users on catalog usage
