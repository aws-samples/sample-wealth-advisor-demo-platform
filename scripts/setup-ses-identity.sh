#!/usr/bin/env bash
# Verify an SES email identity for the scheduler email sender.
# Usage: ./scripts/setup-ses-identity.sh <email-address> [region]
#
# After running, check your inbox and click the verification link.
# Then deploy with: pnpm nx deploy @wealth-management-portal/infra -- -c sesSenderEmail=<email-address>

set -euo pipefail

EMAIL="${1:?Usage: $0 <email-address> [region]}"
REGION="${2:-us-west-2}"

echo "Checking existing SES identities in ${REGION}..."
EXISTING=$(aws sesv2 list-email-identities --region "$REGION" --query "EmailIdentities[?IdentityName=='${EMAIL}'].IdentityName" --output text)

if [ -n "$EXISTING" ]; then
  STATUS=$(aws sesv2 get-email-identity --email-identity "$EMAIL" --region "$REGION" --query "VerifiedForSendingStatus" --output text)
  if [ "$STATUS" = "True" ]; then
    echo "✅ ${EMAIL} is already verified in ${REGION}."
    exit 0
  fi
  echo "⏳ ${EMAIL} exists but is not yet verified. Check your inbox for the verification link."
  exit 0
fi

echo "Creating SES email identity for ${EMAIL} in ${REGION}..."
aws sesv2 create-email-identity --email-identity "$EMAIL" --region "$REGION"
echo "📧 Verification email sent to ${EMAIL}. Click the link in your inbox to complete setup."
