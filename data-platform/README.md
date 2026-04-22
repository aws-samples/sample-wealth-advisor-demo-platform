# Financial Advisor Data Analytics Platform on AWS

A data analytics and AI platform for financial advisory services, built on AWS using Terraform. This solution is based on the [DAIVI](https://github.com/aws-samples/sample-pace-data-analytics-ml-ai) reference architecture and adapted for financial advisor use cases.

## Table of Contents

- [About](#about)
- [Solution Components](#solution-components)
- [Financial Advisor Data Lake](#financial-advisor-data-lake)
- [Deployment](#deployment)
- [Contributors](#contributors)

## About

This solution provides Terraform modules to build a financial advisor data platform on AWS using **Amazon SageMaker Unified Studio**. It provisions a complete data lake with 24 financial advisor datasets, Glue batch pipelines, Redshift views, and visualization through QuickSight.

The platform supports the following capabilities:

1. IAM Identity Center for user and group management with role-based access
2. Iceberg data lakes on S3 table buckets for financial advisor data
3. SageMaker domains and projects with Lakehouse integration
4. SageMaker Catalog for data assets, lineage, and data quality
5. DataZone for data governance and data mesh
6. Glue batch pipelines, Athena for data exploration, Redshift for analytics, and QuickSight for visualization

## Solution Components

### Data Lakes

The solution provisions Iceberg data lakes on S3 table buckets containing 24 financial advisor datasets including clients, advisors, accounts, portfolios, securities, transactions, holdings, market data, performance, fees, goals, interactions, documents, compliance, research, articles, and more.

### Data Pipelines

The solution uses Glue batch data pipelines to load CSV data files into Iceberg tables on S3 table buckets. Each of the 24 datasets has a dedicated Glue job.

### IAM Identity Center

Modules to provision IAM Identity Center instances (organization-level or account-level), create users and groups, and grant required permissions.

### SageMaker Unified Studio

Modules to provision SageMaker domains and projects with IAM Identity Center integration. The solution creates one domain with two projects: producer and consumer.

### SageMaker Lakehouse

Modules to configure SageMaker projects to load data lakes into SageMaker Lakehouse for querying via Athena and Redshift.

### Redshift Analytics

Redshift Serverless views are created in the producer project's workgroup to provide analytical views over the financial advisor data, including advisor dashboards, client portfolios, AUM tracking, and more.

### SageMaker Catalog

Modules to create data sources, load assets from data lakes, view data quality and data lineage, and create custom assets and custom lineage.

### QuickSight Visualization

Modules to create dashboards and visualizations using QuickSight, leveraging data from the financial advisor data lake.

## Financial Advisor Data Lake

The solution implements a financial advisor data lake with 24 datasets loaded into Iceberg tables on S3 table buckets via Glue batch pipelines.

### Datasets

| Category | Tables |
| --- | --- |
| Core | clients, advisors, accounts, portfolios, securities |
| Transactions | transactions, holdings, fees, market_data, performance |
| Client Management | goals, interactions, documents, compliance, client_reports |
| Client Details | client_income_expense, client_investment_restrictions |
| Research & Content | research, articles, themes, theme_article_associations, crawl_log |
| Configuration | portfolio_config, recommended_products |

## Deployment

The solution is deployed incrementally using Make targets. See the [Solutions Deployment Guide](./docs/main/solutions-deployment.md) for step-by-step instructions.

### Deployment Modules

| Order | Module |
| --- | --- |
| 1 | Foundation (KMS, IAM, S3, VPC, MSK) |
| 2 | IAM Identity Center |
| 3 | SageMaker Domain |
| 4 | SageMaker Projects |
| 5 | Glue Iceberg Jar File |
| 6 | Lake Formation |
| 7 | Athena |
| 8-9 | Financial Advisor Data Lake |
| 10 | SageMaker Project Configuration |
| 11 | DataZone Domain and Projects |
| 12-13 | QuickSight Subscription and Visualization |
| 14 | Custom Data Lineage |
| 15 | EMR Serverless with Jupyter Notebook |
| 16 | Spark Code Interpreter |

### Quick Start

See the [Solutions Deployment Guide](./docs/main/solutions-deployment.md) for step-by-step instructions.