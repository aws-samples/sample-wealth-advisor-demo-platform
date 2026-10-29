#!/bin/bash
# Create Athena views for the S3 Tables (Iceberg) catalog.
# These views are used by the API layer to serve dashboard data.
#
# Prerequisites:
#   - S3 Tables infrastructure deployed (s3table.tf)
#   - Glue jobs have loaded seed data
#   - ATHENA_OUTPUT_LOCATION set (S3 path for query results)
#
# Usage: ./scripts/setup-athena-views.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SQL_FILE="$REPO_ROOT/data-platform/ddl-athena/create-views.sql"

REGION="${AWS_REGION:-ap-southeast-2}"
WORKGROUP="${ATHENA_WORKGROUP:-primary}"
CATALOG="${ATHENA_CATALOG:-s3tablescatalog/financial-advisor-s3table}"
DATABASE="${ATHENA_DATABASE:-financial_advisor}"
OUTPUT_LOCATION="${ATHENA_OUTPUT_LOCATION:-}"

if [ -z "$OUTPUT_LOCATION" ]; then
    echo "ERROR: ATHENA_OUTPUT_LOCATION must be set (e.g., s3://my-bucket/athena-results/)"
    exit 1
fi

echo "=== Creating Athena Views ==="
echo "  Region:    $REGION"
echo "  Workgroup: $WORKGROUP"
echo "  Catalog:   $CATALOG"
echo "  Database:  $DATABASE"
echo "  Output:    $OUTPUT_LOCATION"
echo ""

# Split SQL file by semicolons and execute each statement
IFS=';' read -ra STATEMENTS <<< "$(cat "$SQL_FILE" | sed '/^--/d' | tr '\n' ' ')"

EXECUTED=0
for stmt in "${STATEMENTS[@]}"; do
    # Skip empty statements
    trimmed=$(echo "$stmt" | xargs)
    if [ -z "$trimmed" ]; then
        continue
    fi

    echo "  Executing: $(echo "$trimmed" | head -c 80)..."

    QUERY_ID=$(aws athena start-query-execution \
        --query-string "$trimmed" \
        --work-group "$WORKGROUP" \
        --query-execution-context "Catalog=$CATALOG,Database=$DATABASE" \
        --result-configuration "OutputLocation=$OUTPUT_LOCATION" \
        --region "$REGION" \
        --query "QueryExecutionId" \
        --output text 2>&1)

    if [ $? -ne 0 ]; then
        echo "    FAILED to start: $QUERY_ID"
        continue
    fi

    # Wait for completion
    for i in $(seq 1 30); do
        STATE=$(aws athena get-query-execution \
            --query-execution-id "$QUERY_ID" \
            --region "$REGION" \
            --query "QueryExecution.Status.State" \
            --output text 2>/dev/null)
        if [ "$STATE" = "SUCCEEDED" ]; then
            echo "    OK"
            break
        elif [ "$STATE" = "FAILED" ] || [ "$STATE" = "CANCELLED" ]; then
            REASON=$(aws athena get-query-execution \
                --query-execution-id "$QUERY_ID" \
                --region "$REGION" \
                --query "QueryExecution.Status.StateChangeReason" \
                --output text 2>/dev/null)
            echo "    FAILED: $REASON"
            break
        fi
        sleep 2
    done

    EXECUTED=$((EXECUTED + 1))
done

echo ""
echo "=== Done. Executed $EXECUTED statements. ==="
