#!/usr/bin/env bash
# Deploy the entire platform (data-platform + app CDK stack) to a fresh AWS region.
#
# Usage:
#   ./scripts/deploy-fresh-region.sh us-west-2
#
# Prerequisites:
#   - AWS credentials configured (Admin role recommended for initial deploy)
#   - data-platform/init.sh has been run at least once (generates Makefile from template)
#   - Node.js, pnpm, Terraform, and AWS CLI installed
#
# This script deploys in the correct order:
#   Phase 1: Data Platform (Terraform) — VPC, S3 Tables, Glue, Athena, Lake Formation
#   Phase 2: App CDK Stack — Cognito, APIs, Agents, Neptune, CloudFront UI
set -euo pipefail

# ─── Configuration ────────────────────────────────────────────────────────────
TARGET_REGION="${1:?Usage: $0 <aws-region> (e.g. us-west-2)}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_PLATFORM_DIR="$REPO_ROOT/data-platform"

echo "═══════════════════════════════════════════════════════════════"
echo "  Deploying Wealth Management Portal to: $TARGET_REGION"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# ─── Validate prerequisites ──────────────────────────────────────────────────
echo "▶ Checking prerequisites..."

if ! command -v aws &>/dev/null; then
  echo "ERROR: aws CLI not found. Install it first." >&2; exit 1
fi
if ! command -v terraform &>/dev/null; then
  echo "ERROR: terraform not found. Install it first." >&2; exit 1
fi
if ! command -v pnpm &>/dev/null; then
  echo "ERROR: pnpm not found. Install it first." >&2; exit 1
fi

# Verify AWS credentials are valid and explicitly target the intended account.
EXPECTED_AWS_ACCOUNT_ID="${EXPECTED_AWS_ACCOUNT_ID:?Set EXPECTED_AWS_ACCOUNT_ID to the intended 12-digit AWS account before deploying}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null) || {
  echo "ERROR: AWS credentials not configured or expired." >&2
  echo "  Refresh credentials for the intended account, then retry." >&2
  exit 1
}
if [[ "$AWS_ACCOUNT_ID" != "$EXPECTED_AWS_ACCOUNT_ID" ]]; then
  echo "ERROR: AWS account mismatch. Expected $EXPECTED_AWS_ACCOUNT_ID, got $AWS_ACCOUNT_ID." >&2
  exit 1
fi
echo "  Account: $AWS_ACCOUNT_ID"
echo "  Region:  $TARGET_REGION"
echo ""

# Update one KEY=value entry using portable sed syntax.
replace_env_value() {
  local key="$1" value="$2"
  if grep -q "^${key}=" "$ENV_FILE"; then
    if [[ "$OSTYPE" == darwin* ]]; then
      sed -i '' "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
    else
      sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
    fi
  else
    echo "${key}=${value}" >> "$ENV_FILE"
  fi
}

# ─── Phase 0: Update .env with target region ─────────────────────────────────
echo "▶ Phase 0: Configuring .env for $TARGET_REGION"

ENV_FILE="$REPO_ROOT/.env"
if [[ -f "$ENV_FILE" ]]; then
  replace_env_value "AWS_REGION" "$TARGET_REGION"
else
  echo "AWS_REGION=$TARGET_REGION" > "$ENV_FILE"
fi

# Clear stale CDK context (VPC lookups cached from previous region)
CDK_CONTEXT="$REPO_ROOT/cdk.context.json"
if [[ -f "$CDK_CONTEXT" ]]; then
  echo "  Clearing stale cdk.context.json (cached for previous region)"
  echo "{}" > "$CDK_CONTEXT"
fi

echo "  .env updated: AWS_REGION=$TARGET_REGION"
echo ""

# ─── Phase 1: Data Platform (Terraform) ──────────────────────────────────────
echo "═══════════════════════════════════════════════════════════════"
echo "  Phase 1: Data Platform (Athena + S3 Tables)"
echo "═══════════════════════════════════════════════════════════════"
echo ""

if [[ ! -f "$DATA_PLATFORM_DIR/Makefile" ]] || ! grep -q "^AWS_DEFAULT_REGION" "$DATA_PLATFORM_DIR/Makefile"; then
  echo "▶ Data platform not initialized. Running init.sh..."
  echo "  You will be prompted for: account ID, app name, env name, regions, admin role."
  echo ""
  (cd "$DATA_PLATFORM_DIR" && ./init.sh)
  echo ""
fi

# Verify the generated Makefile targets the right region
if grep -q "^AWS_PRIMARY_REGION" "$DATA_PLATFORM_DIR/Makefile"; then
  DP_REGION=$(grep "^AWS_PRIMARY_REGION" "$DATA_PLATFORM_DIR/Makefile" | head -1 | awk '{print $3}')
  if [[ "$DP_REGION" != "$TARGET_REGION" ]]; then
    echo "WARNING: data-platform Makefile targets '$DP_REGION' but you requested '$TARGET_REGION'."
    echo "  Re-run 'make init' in data-platform/ with PRIMARY_REGION=$TARGET_REGION"
    echo "  Or press Enter to continue anyway (Ctrl+C to abort)."
    read -r
  fi
fi

echo "▶ Step 1.1: Deploy Terraform backend (CloudFormation S3 bucket for state)"
(cd "$DATA_PLATFORM_DIR" && make deploy-tf-backend-cf-stack)
echo ""

echo "▶ Step 1.2: Deploy foundation (KMS, IAM roles, S3 buckets, VPC)"
(cd "$DATA_PLATFORM_DIR" && make deploy-foundation)
echo ""

echo "▶ Step 1.3: Set up Lake Formation admin + S3 Tables catalog"
(cd "$DATA_PLATFORM_DIR" && make set-up-lake-formation-admin-role)
(cd "$DATA_PLATFORM_DIR" && make create-glue-s3tables-catalog)
(cd "$DATA_PLATFORM_DIR" && make register-s3table-catalog-with-lake-formation)
(cd "$DATA_PLATFORM_DIR" && make grant-default-database-permissions)
(cd "$DATA_PLATFORM_DIR" && make drop-default-database)
echo ""

echo "▶ Step 1.4: Deploy Athena workgroup"
(cd "$DATA_PLATFORM_DIR" && make deploy-athena)
echo ""

echo "▶ Step 1.5: Deploy Glue JARs + S3 Tables datalake + run Glue jobs"
# Create placeholder SSM param required by datalake TF (normally set by SageMaker domain deploy)
APP_NAME=$(grep "^APP_NAME" "$DATA_PLATFORM_DIR/Makefile" | awk '{print $3}')
ENV_NAME=$(grep "^ENV_NAME" "$DATA_PLATFORM_DIR/Makefile" | awk '{print $3}')
aws ssm put-parameter --name "/${APP_NAME}/${ENV_NAME}/smus_domain_id" \
  --value "placeholder" --type String --region "$TARGET_REGION" --overwrite 2>/dev/null || true
(cd "$DATA_PLATFORM_DIR" && make deploy-glue-jars)
(cd "$DATA_PLATFORM_DIR" && make deploy-financial-advisor-s3-glue-s3)
(cd "$DATA_PLATFORM_DIR" && make start-financial-advisor-glue-jobs)
echo ""

echo "▶ Step 1.6: Grant Lake Formation permissions on S3 Tables"
(cd "$DATA_PLATFORM_DIR" && make grant-s3table-lakeformation-permissions)
echo ""

echo "  ✓ Data Platform deployed successfully"
echo ""

# ─── Extract VPC outputs for CDK stack ────────────────────────────────────────
echo "▶ Extracting VPC/networking outputs from data-platform for CDK..."

# Get VPC ID from Terraform state
VPC_ID=$(cd "$DATA_PLATFORM_DIR/iac/roots/foundation/vpc" && terraform output -raw vpc_id 2>/dev/null) || {
  echo "  Could not read VPC ID from Terraform output."
  echo "  Attempting to read from SSM..."
  APP_NAME=$(grep "^APP_NAME" "$DATA_PLATFORM_DIR/Makefile" | awk '{print $3}')
  ENV_NAME=$(grep "^ENV_NAME" "$DATA_PLATFORM_DIR/Makefile" | awk '{print $3}')
  VPC_ID=$(aws ssm get-parameter --name "/${APP_NAME}/${ENV_NAME}/vpc_id" --query "Parameter.Value" --output text --region "$TARGET_REGION" 2>/dev/null) || true
}

PRIVATE_SUBNETS=$(cd "$DATA_PLATFORM_DIR/iac/roots/foundation/vpc" && terraform output -raw private_subnet_ids 2>/dev/null) || {
  PRIVATE_SUBNETS=$(aws ssm get-parameter --name "/${APP_NAME}/${ENV_NAME}/vpc_private_subnet_ids" --query "Parameter.Value" --output text --region "$TARGET_REGION" 2>/dev/null) || true
}

SECURITY_GROUP=$(cd "$DATA_PLATFORM_DIR/iac/roots/foundation/vpc" && terraform output -raw security_group_id 2>/dev/null) || {
  SECURITY_GROUP=$(aws ssm get-parameter --name "/${APP_NAME}/${ENV_NAME}/sagemaker/producer/security-group" --query "Parameter.Value" --output text --region "$TARGET_REGION" 2>/dev/null) || true
}

ROUTE_TABLE=$(cd "$DATA_PLATFORM_DIR/iac/roots/foundation/vpc" && terraform output -raw private_route_table_id 2>/dev/null) || {
  ROUTE_TABLE=$(aws ssm get-parameter --name "/${APP_NAME}/${ENV_NAME}/vpc_private_route_table_id" --query "Parameter.Value" --output text --region "$TARGET_REGION" 2>/dev/null) || true
}

# Update .env with extracted values
update_env() {
  local key="$1" value="$2"
  if [[ -n "$value" && "$value" != "None" ]]; then
    if grep -q "^${key}=" "$ENV_FILE"; then
      if [[ "$OSTYPE" == darwin* ]]; then
        sed -i '' "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
      else
        sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
      fi
    else
      echo "${key}=${value}" >> "$ENV_FILE"
    fi
    echo "  ${key}=${value}"
  fi
}

update_env "REDSHIFT_VPC_ID" "$VPC_ID"
update_env "PRIVATE_SUBNET_IDS" "$PRIVATE_SUBNETS"
update_env "REDSHIFT_SECURITY_GROUP_ID" "$SECURITY_GROUP"
update_env "PRIVATE_ROUTE_TABLE_ID" "$ROUTE_TABLE"

# Ensure Athena config is set
update_env "DATA_ENGINE" "athena"
update_env "ATHENA_WORKGROUP" "primary"
update_env "ATHENA_CATALOG" "s3tablescatalog/financial-advisor-s3table"
update_env "ATHENA_DATABASE" "financial_advisor"
update_env "ATHENA_OUTPUT_LOCATION" "s3://${AWS_ACCOUNT_ID}-$(grep '^APP_NAME' "$DATA_PLATFORM_DIR/Makefile" | awk '{print $3}')-$(grep '^ENV_NAME' "$DATA_PLATFORM_DIR/Makefile" | awk '{print $3}')-${TARGET_REGION}-glue-temp/athena-results/"

# Derive Bedrock model region prefix from target region
case "$TARGET_REGION" in
  us-*) MODEL_PREFIX="us" ;;
  ap-southeast-2) MODEL_PREFIX="au" ;;
  eu-*) MODEL_PREFIX="eu" ;;
  ap-*) MODEL_PREFIX="ap" ;;
  *) MODEL_PREFIX="us" ;;
esac

update_env "REPORT_BEDROCK_MODEL_ID" "${MODEL_PREFIX}.anthropic.claude-sonnet-5"
update_env "THEME_BEDROCK_MODEL_ID" "${MODEL_PREFIX}.anthropic.claude-sonnet-5"
update_env "DD_BEDROCK_MODEL_ID" "${MODEL_PREFIX}.anthropic.claude-sonnet-5"
update_env "ROUTING_BEDROCK_MODEL_ID" "${MODEL_PREFIX}.anthropic.claude-haiku-4-5-20251001-v1:0"
update_env "SUBAGENT_BEDROCK_MODEL_ID" "${MODEL_PREFIX}.anthropic.claude-haiku-4-5-20251001-v1:0"
update_env "STOCK_AGENT_BEDROCK_MODEL_ID" "${MODEL_PREFIX}.anthropic.claude-sonnet-5"
update_env "CLIENT_SEARCH_MODEL_ID" "${MODEL_PREFIX}.anthropic.claude-sonnet-5"

echo ""

# ─── Phase 2: CDK App Stack ──────────────────────────────────────────────────
echo "═══════════════════════════════════════════════════════════════"
echo "  Phase 2: App CDK Stack"
echo "═══════════════════════════════════════════════════════════════"
echo ""

echo "▶ Step 2.1: Install dependencies"
(cd "$REPO_ROOT" && pnpm install --frozen-lockfile)
echo ""

echo "▶ Step 2.2: CDK Bootstrap in $TARGET_REGION"
(cd "$REPO_ROOT" && pnpm nx bootstrap @wealth-management-portal/infra)
echo ""

echo "▶ Step 2.3: Build all packages (UI, APIs, Lambdas)"
(cd "$REPO_ROOT" && pnpm nx run-many --target=build --all --exclude=@wealth-management-portal/infra)
echo ""

echo "▶ Step 2.4: CDK Deploy"
(cd "$REPO_ROOT" && pnpm nx deploy @wealth-management-portal/infra)
echo ""

echo "  ✓ App CDK Stack deployed successfully"
echo ""

# ─── Phase 3: Post-deployment setup ──────────────────────────────────────────
echo "═══════════════════════════════════════════════════════════════"
echo "  Phase 3: Post-deployment setup"
echo "═══════════════════════════════════════════════════════════════"
echo ""

echo "▶ Step 3.1: Create test user"
(cd "$REPO_ROOT" && pnpm nx create-user @wealth-management-portal/infra) || echo "  (skipped — may need manual setup)"
echo ""

echo "▶ Step 3.2: Grant Lake Formation permissions to CDK Lambdas"
(cd "$REPO_ROOT" && pnpm nx grant-lf-permissions @wealth-management-portal/infra) || echo "  (skipped)"
echo ""

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ✓ Deployment complete!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "  Region:  $TARGET_REGION"
echo "  Account: $AWS_ACCOUNT_ID"
echo ""
echo "  Next steps:"
echo "    1. Check CloudFormation console for stack outputs (CloudFront URL, API URLs)"
echo "    2. Run 'pnpm nx create-user @wealth-management-portal/infra' to add more users"
echo "    3. Optionally load Neptune graph data: python scripts/load-neptune-data.py"
echo ""
