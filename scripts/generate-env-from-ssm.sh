#!/usr/bin/env bash
set -euo pipefail

# Generates .env from environment variables (injected by CodeBuild from SSM).
# Auto-discovers VPC, subnet, security group, route table, and Redshift
# workgroup from data-platform SSM params when not already set.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"

# ── Bootstrap: resolve region, app name, env name ────────────────────
# When running locally (outside CodeBuild), these env vars won't be set.
# Resolve them from SSM or AWS CLI config so the script is hands-free.
AWS_REGION="${AWS_REGION:-$(aws configure get region 2>/dev/null || echo "us-west-2")}"

# Fetch a single SSM parameter, returns empty string on failure
fetch_ssm() {
  aws ssm get-parameter --name "$1" --with-decryption \
    --query 'Parameter.Value' --output text \
    --region "${AWS_REGION}" 2>/dev/null || echo ""
}

# Resolve the data-platform app/env names (needed to build SSM paths)
APP_NAME="${APP_NAME:-$(fetch_ssm /wealth-management-portal/platform/app-name)}"
ENV_NAME="${ENV_NAME:-$(fetch_ssm /wealth-management-portal/platform/env-name)}"
DP_APP="$APP_NAME"
DP_ENV="$ENV_NAME"

if [[ -n "$DP_APP" && -n "$DP_ENV" ]]; then
  DP="/${DP_APP}/${DP_ENV}"
  echo "Auto-discovering infrastructure from ${DP}/..."

  # VPC ID
  if [[ -z "${REDSHIFT_VPC_ID:-}" ]]; then
    REDSHIFT_VPC_ID="$(fetch_ssm "${DP}/vpc_id")"
    [[ -n "$REDSHIFT_VPC_ID" ]] && echo "  ✓ REDSHIFT_VPC_ID=${REDSHIFT_VPC_ID}"
  fi

  # Private subnet IDs
  if [[ -z "${PRIVATE_SUBNET_IDS:-}" ]]; then
    PRIVATE_SUBNET_IDS="$(fetch_ssm "${DP}/vpc_private_subnet_ids")"
    [[ -n "$PRIVATE_SUBNET_IDS" ]] && echo "  ✓ PRIVATE_SUBNET_IDS=${PRIVATE_SUBNET_IDS}"
  fi

  # Security group — try producer project first, fall back to VPC-level
  if [[ -z "${REDSHIFT_SECURITY_GROUP_ID:-}" ]]; then
    REDSHIFT_SECURITY_GROUP_ID="$(fetch_ssm "${DP}/sagemaker/producer/security-group")"
    if [[ -z "$REDSHIFT_SECURITY_GROUP_ID" ]]; then
      REDSHIFT_SECURITY_GROUP_ID="$(fetch_ssm "${DP}/vpc-sg")"
    fi
    [[ -n "$REDSHIFT_SECURITY_GROUP_ID" ]] && echo "  ✓ REDSHIFT_SECURITY_GROUP_ID=${REDSHIFT_SECURITY_GROUP_ID}"
  fi

  # Private route table ID
  if [[ -z "${PRIVATE_ROUTE_TABLE_ID:-}" ]]; then
    PRIVATE_ROUTE_TABLE_ID="$(fetch_ssm "${DP}/vpc_private_route_table_id")"
    [[ -n "$PRIVATE_ROUTE_TABLE_ID" ]] && echo "  ✓ PRIVATE_ROUTE_TABLE_ID=${PRIVATE_ROUTE_TABLE_ID}"
  fi

  # Redshift workgroup — derived from producer project's redshift-env-id
  if [[ -z "${REDSHIFT_WORKGROUP:-}" ]]; then
    env_id="$(fetch_ssm "${DP}/sagemaker/producer/redshift-env-id")"
    if [[ -n "$env_id" ]]; then
      REDSHIFT_WORKGROUP="redshift-serverless-workgroup-${env_id}"
      echo "  ✓ REDSHIFT_WORKGROUP=${REDSHIFT_WORKGROUP}"
    fi
  fi

  # Private subnet AZ — derived from first subnet
  if [[ -z "${PRIVATE_SUBNET_AZ:-}" && -n "${PRIVATE_SUBNET_IDS:-}" ]]; then
    first_subnet="${PRIVATE_SUBNET_IDS%%,*}"
    PRIVATE_SUBNET_AZ="$(aws ec2 describe-subnets --subnet-ids "$first_subnet" \
      --query 'Subnets[0].AvailabilityZone' --output text \
      --region "${AWS_REGION}" 2>/dev/null || echo "")"
    [[ -n "$PRIVATE_SUBNET_AZ" ]] && echo "  ✓ PRIVATE_SUBNET_AZ=${PRIVATE_SUBNET_AZ}"
  fi
else
  echo "WARNING: Could not determine data-platform app/env names — skipping auto-discovery." >&2
fi

# ── Resolve app-level SSM params when not already in env ─────────────
REDSHIFT_DATABASE="${REDSHIFT_DATABASE:-$(fetch_ssm /wealth-management-portal/redshift-database)}"
SES_SENDER_EMAIL="${SES_SENDER_EMAIL:-$(fetch_ssm /wealth-management-portal/ses-sender-email)}"
REPORT_BEDROCK_MODEL_ID="${REPORT_BEDROCK_MODEL_ID:-$(fetch_ssm /wealth-management-portal/report-bedrock-model-id)}"
TAVILY_API_KEY="${TAVILY_API_KEY:-$(fetch_ssm /wealth-management-portal/tavily-api-key)}"
THEME_BEDROCK_MODEL_ID="${THEME_BEDROCK_MODEL_ID:-$(fetch_ssm /wealth-management-portal/theme-bedrock-model-id)}"
DEPLOY_BASTION="${DEPLOY_BASTION:-$(fetch_ssm /wealth-management-portal/deploy-bastion)}"
NEPTUNE_GRAPH_ID="${NEPTUNE_GRAPH_ID:-$(fetch_ssm /wealth-management-portal/neptune-graph-id)}"

# ── Discover deployed AgentCore resources ────────────────────────────
# Portfolio gateway URL and report S3 bucket from the report agent runtime
if [[ -z "${PORTFOLIO_GATEWAY_URL:-}" || -z "${REPORT_S3_BUCKET:-}" ]]; then
  RUNTIME_ID=$(aws bedrock-agentcore-control list-agent-runtimes --region "${AWS_REGION}" \
    --query "agentRuntimes[?contains(agentRuntimeName,'Report')].agentRuntimeId | [0]" --output text 2>/dev/null || echo "")
  if [[ -n "$RUNTIME_ID" && "$RUNTIME_ID" != "None" ]]; then
    RUNTIME_ENV=$(aws bedrock-agentcore-control get-agent-runtime --agent-runtime-id "$RUNTIME_ID" \
      --region "${AWS_REGION}" --query "environmentVariables" --output json 2>/dev/null || echo "{}")
    if [[ -z "${PORTFOLIO_GATEWAY_URL:-}" ]]; then
      PORTFOLIO_GATEWAY_URL=$(echo "$RUNTIME_ENV" | python3 -c "import sys,json; print(json.load(sys.stdin).get('PORTFOLIO_GATEWAY_URL',''))" 2>/dev/null || echo "")
      [[ -n "$PORTFOLIO_GATEWAY_URL" ]] && echo "  ✓ PORTFOLIO_GATEWAY_URL=${PORTFOLIO_GATEWAY_URL}"
    fi
    if [[ -z "${REPORT_S3_BUCKET:-}" ]]; then
      REPORT_S3_BUCKET=$(echo "$RUNTIME_ENV" | python3 -c "import sys,json; print(json.load(sys.stdin).get('REPORT_S3_BUCKET',''))" 2>/dev/null || echo "")
      [[ -n "$REPORT_S3_BUCKET" ]] && echo "  ✓ REPORT_S3_BUCKET=${REPORT_S3_BUCKET}"
    fi
  fi
fi

# ── Validate required variables ──────────────────────────────────────
missing=()
for var in AWS_REGION REDSHIFT_WORKGROUP REDSHIFT_DATABASE REDSHIFT_VPC_ID \
           PRIVATE_SUBNET_IDS REDSHIFT_SECURITY_GROUP_ID PRIVATE_ROUTE_TABLE_ID; do
  [[ -z "${!var:-}" ]] && missing+=("$var")
done

if [[ ${#missing[@]} -gt 0 ]]; then
  echo "ERROR: Missing required variables (not in env and not discoverable from data-platform SSM): ${missing[*]}" >&2
  exit 1
fi

# ── Write .env ───────────────────────────────────────────────────────
cat > "$ENV_FILE" <<EOF
AWS_REGION=${AWS_REGION}
AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}
USE_DEFAULT_AWS_CREDENTIALS=true
REDSHIFT_WORKGROUP=${REDSHIFT_WORKGROUP}
REDSHIFT_DATABASE=${REDSHIFT_DATABASE}
REDSHIFT_VPC_ID=${REDSHIFT_VPC_ID}
PRIVATE_SUBNET_IDS=${PRIVATE_SUBNET_IDS}
REDSHIFT_SECURITY_GROUP_ID=${REDSHIFT_SECURITY_GROUP_ID}
PRIVATE_ROUTE_TABLE_ID=${PRIVATE_ROUTE_TABLE_ID}
REPORT_BEDROCK_MODEL_ID=${REPORT_BEDROCK_MODEL_ID:-us.anthropic.claude-sonnet-4-5-20250929-v1:0}
THEME_BEDROCK_MODEL_ID=${THEME_BEDROCK_MODEL_ID:-us.anthropic.claude-sonnet-4-5-20250929-v1:0}
DEPLOY_BASTION=${DEPLOY_BASTION:-false}
NEPTUNE_GRAPH_ID=${NEPTUNE_GRAPH_ID:-}
PRIVATE_SUBNET_AZ=${PRIVATE_SUBNET_AZ:-}
SES_SENDER_EMAIL=${SES_SENDER_EMAIL:-}
TAVILY_API_KEY=${TAVILY_API_KEY:-}
STAGE_NAME=${STAGE_NAME:-sandbox}
ENABLE_COMPLIANCE_REPORTING=${ENABLE_COMPLIANCE_REPORTING:-false}
COMPLIANCE_REPORTING_BUCKET=${COMPLIANCE_REPORTING_BUCKET:-}
PORTFOLIO_GATEWAY_URL=${PORTFOLIO_GATEWAY_URL:-}
REPORT_S3_BUCKET=${REPORT_S3_BUCKET:-}
EOF

echo "Generated $ENV_FILE"
