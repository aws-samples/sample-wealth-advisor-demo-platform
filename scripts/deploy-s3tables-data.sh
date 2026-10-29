#!/bin/bash
# Deploy S3 Tables infrastructure and load seed data via Glue jobs.
# Prerequisites:
#   - AWS credentials configured for the target account
#   - Terraform >= 1.8.0 installed
#   - The following resources must exist (created by earlier data-platform make targets):
#     * KMS keys (S3, S3 Tables, Glue, CloudWatch)
#     * Glue IAM role
#     * Glue scripts S3 bucket
#     * Source data S3 bucket
#
# Usage: ./scripts/deploy-s3tables-data.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TF_ROOT="$REPO_ROOT/data-platform/iac/roots/datalakes/financial-advisor-s3-glue-s3"
DATA_DIR="$REPO_ROOT/data-platform/data/financial_advisor"

echo "=== S3 Tables + Glue Data Deployment ==="
echo ""

# Check for terraform.tfvars
if [ ! -f "$TF_ROOT/terraform.tfvars" ]; then
    echo "ERROR: $TF_ROOT/terraform.tfvars not found."
    echo ""
    echo "Create it with the following variables:"
    echo '  AWS_ACCOUNT_ID         = "your-account-id"'
    echo '  APP                    = "wealth-mgmt"'
    echo '  ENV                    = "dev"'
    echo '  AWS_PRIMARY_REGION     = "ap-southeast-2"'
    echo '  S3_KMS_KEY_ALIAS       = "your-s3-kms-key-alias"'
    echo '  S3_TABLES_KMS_KEY_ALIAS = "your-s3tables-kms-key-alias"'
    echo '  GLUE_SCRIPTS_BUCKET_NAME = "your-glue-scripts-bucket"'
    echo '  GLUE_ROLE_NAME         = "your-glue-role-name"'
    echo '  GLUE_KMS_KEY_ALIAS     = "your-glue-kms-key-alias"'
    echo '  CLOUDWATCH_KMS_KEY_ALIAS = "your-cw-kms-key-alias"'
    exit 1
fi

# Step 1: Deploy Terraform (S3 Table bucket, namespace, tables, Glue jobs)
echo "Step 1: Deploying S3 Tables infrastructure via Terraform..."
cd "$TF_ROOT"
terraform init -upgrade
terraform apply -auto-approve
echo "  Done."
echo ""

# Step 2: Upload seed CSVs to the source S3 bucket
# The Glue jobs read from an S3 bucket. Get the bucket name from Terraform output.
SOURCE_BUCKET=$(terraform output -raw data_bucket_name 2>/dev/null || echo "")
if [ -z "$SOURCE_BUCKET" ]; then
    echo "WARNING: Could not determine source data bucket from Terraform outputs."
    echo "Please set SOURCE_BUCKET and re-run, or upload CSVs manually."
    echo ""
    echo "Expected: aws s3 cp $DATA_DIR/ s3://BUCKET/ --recursive --exclude '*' --include '*.csv'"
    exit 1
fi

# The Glue jobs read SOURCE_PATH = s3://BUCKET/<table>.csv (bucket root), and
# Terraform (bucket.tf) uploads the CSVs there. Upload to the same root so this
# script and Terraform agree on one location.
echo "Step 2: Uploading seed CSV data to s3://$SOURCE_BUCKET/ ..."
aws s3 cp "$DATA_DIR/" "s3://$SOURCE_BUCKET/" --recursive --exclude '*' --include '*.csv' --quiet
echo "  Uploaded $(ls "$DATA_DIR"/*.csv | wc -l | tr -d ' ') CSV files."
echo ""

# Step 3: Start all Glue ETL jobs
echo "Step 3: Starting Glue ETL jobs to load data into S3 Tables..."
TABLES=(
    clients advisors accounts portfolios securities transactions
    holdings market_data performance fees goals interactions
    documents compliance research articles client_income_expense
    client_investment_restrictions client_reports crawl_log
    portfolio_config recommended_products theme_article_associations themes
)

STARTED=0
for table in "${TABLES[@]}"; do
    JOB_NAME="financial-advisor-load-${table}"
    if aws glue start-job-run --job-name "$JOB_NAME" --region "${AWS_REGION:-ap-southeast-2}" > /dev/null 2>&1; then
        STARTED=$((STARTED + 1))
    else
        echo "  WARNING: Failed to start job $JOB_NAME (may not exist yet)"
    fi
done
echo "  Started $STARTED Glue jobs."
echo ""

# Step 4: Wait for Glue jobs to complete
echo "Step 4: Waiting for Glue jobs to complete (this may take 5-10 minutes)..."
REGION="${AWS_REGION:-ap-southeast-2}"
MAX_WAIT=600
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
    RUNNING=$(aws glue get-job-runs --job-name "financial-advisor-load-clients" --region "$REGION" --max-results 1 --query "JobRuns[0].JobRunState" --output text 2>/dev/null || echo "UNKNOWN")
    if [ "$RUNNING" = "SUCCEEDED" ] || [ "$RUNNING" = "FAILED" ] || [ "$RUNNING" = "STOPPED" ]; then
        break
    fi
    sleep 15
    ELAPSED=$((ELAPSED + 15))
    echo "  Still running... (${ELAPSED}s elapsed)"
done

echo ""
echo "=== Deployment complete ==="
echo ""
echo "Next steps:"
echo "  1. Verify data: aws athena start-query-execution \\"
echo "       --query-string 'SELECT COUNT(*) FROM clients' \\"
echo "       --work-group primary \\"
echo "       --query-execution-context Catalog=s3tablescatalog/financial-advisor-s3table,Database=financial_advisor"
echo "  2. Set ATHENA_OUTPUT_LOCATION in .env to an S3 path for Athena results"
echo "  3. Redeploy the CDK app stack: pnpm nx deploy @wealth-management-portal/infra"
