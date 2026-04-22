#!/bin/bash
set -euo pipefail

# Configuration
WORKGROUP="${REDSHIFT_WORKGROUP:-financial-advisor-wg}"
DATABASE="${REDSHIFT_DATABASE:-financial-advisor-db}"
REGION="${AWS_REGION:-us-west-2}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_DIR="$SCRIPT_DIR/../data-platform/sql"

SQL_FILES=(
  "create_view_client_portfolio_holdings.sql"
  "create_view_client_portfolio_performance.sql"
  "create_view_client_account_transactions.sql"
)

VIEW_NAMES=(
  "client_portfolio_holdings"
  "client_portfolio_performance"
  "client_account_transactions"
)

execute_and_wait() {
  local sql="$1"
  local label="$2"

  local stmt_id
  stmt_id=$(aws redshift-data execute-statement \
    --region "$REGION" \
    --workgroup-name "$WORKGROUP" \
    --database "$DATABASE" \
    --sql "$sql" \
    --query 'Id' \
    --output text)

  echo "  Statement ID: $stmt_id" >&2

  local status="SUBMITTED"
  while [[ "$status" == "SUBMITTED" || "$status" == "PICKED" || "$status" == "STARTED" ]]; do
    sleep 2
    status=$(aws redshift-data describe-statement \
      --region "$REGION" \
      --id "$stmt_id" \
      --query 'Status' \
      --output text)
  done

  if [[ "$status" != "FINISHED" ]]; then
    local error
    error=$(aws redshift-data describe-statement \
      --region "$REGION" \
      --id "$stmt_id" \
      --query 'Error' \
      --output text)
    echo "✗ $label failed with status: $status" >&2
    echo "  Error: $error" >&2
    exit 1
  fi

  echo "✓ $label completed" >&2
  echo "$stmt_id"
}

echo "Deploying report views to Redshift Serverless..."
echo "  Workgroup: $WORKGROUP"
echo "  Database:  $DATABASE"
echo "  Region:    $REGION"
echo ""

# Create views
for i in "${!SQL_FILES[@]}"; do
  sql_file="$SQL_DIR/${SQL_FILES[$i]}"
  echo "Step $((i+1)): Creating ${VIEW_NAMES[$i]}..."
  sql=$(<"$sql_file")
  execute_and_wait "$sql" "${VIEW_NAMES[$i]}"
  echo ""
done

# Grant SELECT on views to the MCP server's IAM role
STACK_NAME="${STACK_NAME:-wealth-management-portal-infra-sandbox-Application}"
MCP_ROLE=$(aws cloudformation list-stack-resources \
  --region "$REGION" \
  --stack-name "$STACK_NAME" \
  --query "StackResourceSummaries[?ResourceType=='AWS::IAM::Role' && contains(LogicalResourceId, 'PortfolioGatewayHandlerSe')].PhysicalResourceId" \
  --output text)

if [ -n "$MCP_ROLE" ]; then
  echo "Granting SELECT on views to IAMR:${MCP_ROLE}..."
  grant_sql=""
  for view in "${VIEW_NAMES[@]}"; do
    grant_sql+="GRANT SELECT ON public.${view} TO \"IAMR:${MCP_ROLE}\"; "
  done
  execute_and_wait "$grant_sql" "GRANT SELECT to MCP role"
  echo ""
else
  echo "⚠ Could not find MCP server role in stack ${STACK_NAME}, skipping GRANTs"
  echo ""
fi

# Verify views
echo "Verifying views..."
for view in "${VIEW_NAMES[@]}"; do
  echo "  Checking public.$view..."
  stmt_id=$(execute_and_wait "SELECT COUNT(*) FROM public.$view" "$view count")

  result=$(aws redshift-data get-statement-result \
    --region "$REGION" \
    --id "$stmt_id" \
    --query 'Records[0][0].longValue' \
    --output text)

  echo "  → public.$view row count: $result"
  echo ""
done

echo "✓ All report views deployed and verified successfully"
