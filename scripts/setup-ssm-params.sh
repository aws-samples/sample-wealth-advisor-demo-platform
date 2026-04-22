#!/usr/bin/env bash
set -euo pipefail

# Populates SSM parameters for CodeBuild deployments. Only asks for values
# that require human input — infrastructure values (VPC, subnets, etc.) are
# auto-discovered at build time from data-platform SSM params.
#
# Interactive mode (default): prompts for each value with smart defaults.
# Non-interactive mode (--ci): reads from CLI flags or environment variables.
#
# Usage:
#   ./scripts/setup-ssm-params.sh                          # interactive
#   ./scripts/setup-ssm-params.sh --ci --app-name=finadv    # non-interactive

# ── Defaults ─────────────────────────────────────────────────────────
CI_MODE=false
PARAM_APP_NAME="${APP_NAME:-finadv}"
PARAM_ENV_NAME="${ENV_NAME:-dev1}"
PARAM_PRIMARY_REGION=""
PARAM_SECONDARY_REGION=""
PARAM_ADMIN_ROLE="${ADMIN_ROLE:-Admin}"
PARAM_REDSHIFT_DATABASE="${REDSHIFT_DATABASE:-dev}"
PARAM_SES_SENDER_EMAIL="${SES_SENDER_EMAIL:-}"
PARAM_REPORT_BEDROCK_MODEL_ID="${REPORT_BEDROCK_MODEL_ID:-us.anthropic.claude-sonnet-4-5-20250929-v1:0}"
PARAM_TAVILY_API_KEY="${TAVILY_API_KEY:-}"
PARAM_THEME_BEDROCK_MODEL_ID="${THEME_BEDROCK_MODEL_ID:-us.anthropic.claude-sonnet-4-5-20250929-v1:0}"
PARAM_DEPLOY_BASTION="${DEPLOY_BASTION:-false}"
PARAM_TEST_USER_EMAIL="${TEST_USER_EMAIL:-}"
PARAM_TEST_USER_PASSWORD="${TEST_USER_PASSWORD:-}"

# ── Parse CLI flags ──────────────────────────────────────────────────
for arg in "$@"; do
  case "$arg" in
    --ci) CI_MODE=true ;;
    --app-name=*) PARAM_APP_NAME="${arg#*=}" ;;
    --env-name=*) PARAM_ENV_NAME="${arg#*=}" ;;
    --primary-region=*) PARAM_PRIMARY_REGION="${arg#*=}" ;;
    --secondary-region=*) PARAM_SECONDARY_REGION="${arg#*=}" ;;
    --admin-role=*) PARAM_ADMIN_ROLE="${arg#*=}" ;;
    --redshift-database=*) PARAM_REDSHIFT_DATABASE="${arg#*=}" ;;
    --ses-sender-email=*) PARAM_SES_SENDER_EMAIL="${arg#*=}" ;;
    --report-bedrock-model-id=*) PARAM_REPORT_BEDROCK_MODEL_ID="${arg#*=}" ;;
    --tavily-api-key=*) PARAM_TAVILY_API_KEY="${arg#*=}" ;;
    --theme-bedrock-model-id=*) PARAM_THEME_BEDROCK_MODEL_ID="${arg#*=}" ;;
    --deploy-bastion=*) PARAM_DEPLOY_BASTION="${arg#*=}" ;;
    --test-user-email=*) PARAM_TEST_USER_EMAIL="${arg#*=}" ;;
    --test-user-password=*) PARAM_TEST_USER_PASSWORD="${arg#*=}" ;;
    *) echo "Unknown flag: $arg"; exit 1 ;;
  esac
done

# ── Validation ───────────────────────────────────────────────────────
# Same rules as data-platform/init.sh: lowercase alphanumeric, ≤6 chars
validate_name() {
  local value="$1" field="$2"
  if [[ -z "$value" ]]; then
    echo "  ERROR: ${field} cannot be empty." >&2; return 1
  fi
  if [[ ${#value} -gt 6 ]]; then
    echo "  ERROR: ${field} must be 6 characters or fewer (got ${#value})." >&2; return 1
  fi
  if [[ ! "$value" =~ ^[a-z0-9]+$ ]]; then
    echo "  ERROR: ${field} must contain only lowercase letters and numbers." >&2; return 1
  fi
}

# Validates password against Cognito policy: min 8 chars, uppercase,
# lowercase, digit, and symbol required.
validate_password() {
  local value="$1" field="$2"
  if [[ -z "$value" ]]; then
    echo "  ERROR: ${field} cannot be empty." >&2; return 1
  fi
  if [[ ${#value} -lt 8 ]]; then
    echo "  ERROR: ${field} must be at least 8 characters." >&2; return 1
  fi
  if [[ ! "$value" =~ [a-z] ]]; then
    echo "  ERROR: ${field} must contain a lowercase letter." >&2; return 1
  fi
  if [[ ! "$value" =~ [A-Z] ]]; then
    echo "  ERROR: ${field} must contain an uppercase letter." >&2; return 1
  fi
  if [[ ! "$value" =~ [0-9] ]]; then
    echo "  ERROR: ${field} must contain a digit." >&2; return 1
  fi
  if [[ "$value" =~ ^[a-zA-Z0-9]+$ ]]; then
    echo "  ERROR: ${field} must contain a symbol character." >&2; return 1
  fi
}

# ── Auto-detection helpers ───────────────────────────────────────────
detect_account_id() {
  aws sts get-caller-identity --query Account --output text 2>/dev/null || echo ""
}

detect_region() {
  local r="${AWS_DEFAULT_REGION:-}"
  if [[ -z "$r" ]]; then
    r="$(aws configure get region 2>/dev/null || echo "")"
  fi
  echo "${r:-us-west-2}"
}

default_secondary_region() {
  local primary="$1"
  if [[ "$primary" == "us-east-1" ]]; then echo "us-west-2"
  elif [[ "$primary" == "us-west-2" ]]; then echo "us-east-1"
  elif [[ "$primary" == "eu-west-1" ]]; then echo "eu-central-1"
  else echo "us-east-1"
  fi
}

# ── Interactive prompt helper ────────────────────────────────────────
prompt() {
  local varname="$1" description="$2" default="$3"
  if [[ "$CI_MODE" == "true" ]]; then return; fi
  local hint=""
  [[ -n "$default" ]] && hint=" [$default]"
  read -rp "${description}${hint}: " answer
  if [[ -n "$answer" ]]; then
    eval "$varname=\"\$answer\""
  elif [[ -n "$default" ]]; then
    eval "$varname=\"\$default\""
  fi
}

# ── Collect values ───────────────────────────────────────────────────
DETECTED_ACCOUNT_ID="$(detect_account_id)"
DETECTED_REGION="$(detect_region)"

if [[ "$CI_MODE" != "true" ]]; then
  echo ""
  echo "🔧 Wealth Management Portal — SSM Parameter Setup"
  echo ""
  echo "Infrastructure values (VPC, subnets, security groups, Redshift workgroup)"
  echo "are auto-discovered at build time from data-platform SSM parameters."
  echo ""
fi

# Account ID — auto-detected
PARAM_ACCOUNT_ID="${DETECTED_ACCOUNT_ID}"
prompt PARAM_ACCOUNT_ID "AWS Account ID" "$DETECTED_ACCOUNT_ID"

# App name
prompt PARAM_APP_NAME "App name" "$PARAM_APP_NAME"
validate_name "$PARAM_APP_NAME" "APP_NAME"

# Env name
prompt PARAM_ENV_NAME "Env name" "$PARAM_ENV_NAME"
validate_name "$PARAM_ENV_NAME" "ENV_NAME"

# Regions
[[ -z "$PARAM_PRIMARY_REGION" ]] && PARAM_PRIMARY_REGION="$DETECTED_REGION"
prompt PARAM_PRIMARY_REGION "Primary region" "$PARAM_PRIMARY_REGION"

DEFAULT_SECONDARY="$(default_secondary_region "$PARAM_PRIMARY_REGION")"
[[ -z "$PARAM_SECONDARY_REGION" ]] && PARAM_SECONDARY_REGION="$DEFAULT_SECONDARY"
prompt PARAM_SECONDARY_REGION "Secondary region" "$PARAM_SECONDARY_REGION"

# Admin role
prompt PARAM_ADMIN_ROLE "Admin role name" "$PARAM_ADMIN_ROLE"

# App-specific params (not auto-discoverable)
if [[ "$CI_MODE" != "true" ]]; then
  echo ""
  echo "── Application settings ──"
  echo ""
fi

prompt PARAM_REDSHIFT_DATABASE "Redshift database" "$PARAM_REDSHIFT_DATABASE"
prompt PARAM_SES_SENDER_EMAIL "SES sender email (optional)" "$PARAM_SES_SENDER_EMAIL"
prompt PARAM_REPORT_BEDROCK_MODEL_ID "Report Bedrock model" "$PARAM_REPORT_BEDROCK_MODEL_ID"
prompt PARAM_TAVILY_API_KEY "Tavily API key (optional)" "$PARAM_TAVILY_API_KEY"
prompt PARAM_THEME_BEDROCK_MODEL_ID "Theme Bedrock model" "$PARAM_THEME_BEDROCK_MODEL_ID"
prompt PARAM_DEPLOY_BASTION "Deploy bastion (true/false)" "$PARAM_DEPLOY_BASTION"
prompt PARAM_TEST_USER_EMAIL "Test user email" "$PARAM_TEST_USER_EMAIL"
if [[ "$CI_MODE" != "true" ]]; then
  echo "  (min 8 chars, must include: uppercase, lowercase, digit, and symbol)"
fi
prompt PARAM_TEST_USER_PASSWORD "Test user password" "$PARAM_TEST_USER_PASSWORD"
if [[ -n "$PARAM_TEST_USER_PASSWORD" ]]; then
  validate_password "$PARAM_TEST_USER_PASSWORD" "TEST_USER_PASSWORD"
fi

# ── Create Admin IAM role if missing ─────────────────────────────────
create_admin_role() {
  if aws iam get-role --role-name "$PARAM_ADMIN_ROLE" >/dev/null 2>&1; then
    echo "  ✓ IAM role '$PARAM_ADMIN_ROLE' already exists — skipping"
    return
  fi
  echo "  Creating IAM role '$PARAM_ADMIN_ROLE'..."
  aws iam create-role --role-name "$PARAM_ADMIN_ROLE" \
    --assume-role-policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Principal\":{\"AWS\":\"arn:aws:iam::${PARAM_ACCOUNT_ID}:root\"},\"Action\":\"sts:AssumeRole\"}]}" \
    >/dev/null
  aws iam attach-role-policy --role-name "$PARAM_ADMIN_ROLE" \
    --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
  echo "  ✓ IAM role '$PARAM_ADMIN_ROLE' created with AdministratorAccess"
}

if [[ "$CI_MODE" == "true" ]]; then
  create_admin_role
else
  read -rp "Create IAM role '${PARAM_ADMIN_ROLE}' if it doesn't exist? [Y/n]: " create_role
  if [[ "${create_role:-Y}" =~ ^[Yy]$ ]]; then
    create_admin_role
  fi
fi

# ── Write SSM parameters ────────────────────────────────────────────
put_param() {
  local path="$1" value="$2" type="${3:-String}"
  # SSM doesn't allow empty strings; use a space for optional params so
  # CodeBuild parameter-store references don't fail with "does not exist"
  if [[ -z "$value" ]]; then value=" "; fi
  aws ssm put-parameter --name "$path" --value "$value" --type "$type" --overwrite >/dev/null
  echo "  ✓ $path"
}

echo ""
echo "Writing SSM parameters..."

# Platform parameters (used by buildspec-platform.yml)
put_param "/wealth-management-portal/platform/account-id" "$PARAM_ACCOUNT_ID"
put_param "/wealth-management-portal/platform/app-name" "$PARAM_APP_NAME"
put_param "/wealth-management-portal/platform/env-name" "$PARAM_ENV_NAME"
put_param "/wealth-management-portal/platform/primary-region" "$PARAM_PRIMARY_REGION"
put_param "/wealth-management-portal/platform/secondary-region" "$PARAM_SECONDARY_REGION"
put_param "/wealth-management-portal/platform/admin-role" "$PARAM_ADMIN_ROLE"

# Application parameters (used by buildspec-app.yml)
put_param "/wealth-management-portal/aws-region" "$PARAM_PRIMARY_REGION"
put_param "/wealth-management-portal/redshift-database" "$PARAM_REDSHIFT_DATABASE"
put_param "/wealth-management-portal/ses-sender-email" "$PARAM_SES_SENDER_EMAIL"
put_param "/wealth-management-portal/report-bedrock-model-id" "$PARAM_REPORT_BEDROCK_MODEL_ID"
put_param "/wealth-management-portal/tavily-api-key" "$PARAM_TAVILY_API_KEY" "SecureString"
put_param "/wealth-management-portal/theme-bedrock-model-id" "$PARAM_THEME_BEDROCK_MODEL_ID"
put_param "/wealth-management-portal/deploy-bastion" "$PARAM_DEPLOY_BASTION"
put_param "/wealth-management-portal/enable-compliance-reporting" "false"
put_param "/wealth-management-portal/compliance-reporting-bucket" ""
put_param "/wealth-management-portal/test-user-email" "$PARAM_TEST_USER_EMAIL"
put_param "/wealth-management-portal/test-user-password" "$PARAM_TEST_USER_PASSWORD" "SecureString"

echo ""
echo "✓ SSM parameters written."
echo ""
echo "Next steps:"
echo "  1. Deploy CI infrastructure:"
echo "       pnpm install"
echo "       pnpm nx build @wealth-management-portal/ci-infra"
echo "       pnpm nx bootstrap @wealth-management-portal/ci-infra   # first time only"
echo "       pnpm nx deploy @wealth-management-portal/ci-infra"
echo ""
echo "  2. Deploy data platform (Phase 1):"
echo "       ./scripts/upload-source.sh"
echo "       ./scripts/trigger-build.sh wealth-mgmt-platform-deploy buildspec-platform.yml"
echo ""
echo "  3. Deploy application (Phase 2) — infra values auto-discovered:"
echo "       ./scripts/trigger-build.sh wealth-mgmt-deploy buildspec-app.yml"
