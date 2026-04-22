# Financial Advisor Data Lake - S3 Tables

This module creates a financial advisor data lake using AWS S3 Tables with Iceberg format.

## Architecture

- **S3 Table Bucket**: `financial-advisor-s3table`
- **Namespace**: `financial_advisor`
- **Tables**: 15 tables with the same namespace

## Tables

All tables are created based on the CSV files in `/data/financial_advisor/`:

1. **clients** - Client information (100 clients)
2. **advisors** - Financial advisor information (10 advisors)
3. **accounts** - Client accounts (100 accounts)
4. **portfolios** - Investment portfolios (100 portfolios)
5. **securities** - Securities/instruments (150 securities)
6. **transactions** - Financial transactions (1000 transactions)
7. **holdings** - Current portfolio holdings (500 positions)
8. **market_data** - Historical market data (30,000 records)
9. **performance** - Portfolio performance metrics (1200 records)
10. **fees** - Fee transactions (500 fees)
11. **goals** - Client financial goals (100 goals)
12. **interactions** - Client-advisor interactions (200 interactions)
13. **documents** - Document metadata (100 documents)
14. **compliance** - Compliance records (50 records)
15. **research** - Security research reports (100 reports)

## Data Loading Process

Data is loaded using AWS Glue jobs that:
1. Terraform uploads CSV files from local `data/financial_advisor/` to S3 data bucket during deployment
2. Glue jobs read CSV files from the S3 data bucket
3. Glue jobs infer schema automatically
4. Glue jobs load data into S3 Tables using Iceberg format

### Data Flow
```
Local CSV Files (data/financial_advisor/) 
  → Terraform uploads during deploy
  → S3 Data Bucket (financial-advisor-s3-glue-s3-data)
  → Glue Jobs (15 jobs, one per table)
  → S3 Tables (financial_advisor namespace)
```

## Deployment

### 1. Deploy Infrastructure
```bash
make deploy-financial-advisor-s3-glue-s3
```
This creates:
- S3 data bucket
- Uploads all 15 CSV files to the data bucket
- S3 Tables bucket
- Namespace
- 15 Iceberg tables
- 15 Glue jobs for data loading

### 2. Load Data
```bash
make load-financial-advisor-data
```
This starts all 15 Glue jobs to load data from the S3 data bucket into the S3 Tables.

### 3. Destroy
```bash
make destroy-financial-advisor-s3-glue-s3
```

## Configuration

Update `terraform.tfvars` with your AWS account details:
- `AWS_ACCOUNT_ID`: Your AWS account ID
- `APP`: Application name (e.g., "finadv")
- `ENV`: Environment name (e.g., "demo")
- `AWS_PRIMARY_REGION`: Primary AWS region
- `S3_TABLES_KMS_KEY_ALIAS`: KMS key alias for S3 Tables encryption

## Access

The S3 Tables bucket is configured with policies allowing:
- AWS Athena service access
- AWS Glue service access

All tables use the `financial_advisor` namespace for consistent organization.

## Querying Data

After data is loaded, you can query using Athena:

```sql
-- Query clients
SELECT * FROM "s3tablescatalog"."financial_advisor"."clients" LIMIT 10;

-- Join clients with advisors
SELECT c.client_id, c.first_name, c.last_name, a.first_name as advisor_first_name
FROM "s3tablescatalog"."financial_advisor"."clients" c
JOIN "s3tablescatalog"."financial_advisor"."advisors" a ON c.advisor_id = a.advisor_id;
```
