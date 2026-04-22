#!/usr/bin/env bash
set -e

REGION="$1"
APP="$2"
ENV="$3"

# Wait for Identity Center instance to become ACTIVE
echo "Waiting for Identity Center instance to become ACTIVE..."
for i in $(seq 1 30); do
  STATUS=$(aws sso-admin list-instances --region "$REGION" --query 'Instances[0].Status' --output text 2>/dev/null)
  if [ "$STATUS" = "ACTIVE" ]; then
    echo "Identity Center instance is ACTIVE"
    break
  fi
  echo "Status: $STATUS - waiting 10s (attempt $i/30)..."
  sleep 10
done

# Store identity store ID and instance ARN in SSM
IDENTITY_STORE_ID=$(aws sso-admin list-instances --region "$REGION" --query 'Instances[0].IdentityStoreId' --output text)
INSTANCE_ARN=$(aws sso-admin list-instances --region "$REGION" --query 'Instances[0].InstanceArn' --output text)

aws ssm put-parameter \
  --name "/$APP/$ENV/idc/identity-store-id" \
  --value "$IDENTITY_STORE_ID" \
  --type String \
  --overwrite \
  --region "$REGION"

aws ssm put-parameter \
  --name "/$APP/$ENV/idc/instance-arn" \
  --value "$INSTANCE_ARN" \
  --type String \
  --overwrite \
  --region "$REGION"

echo "Stored identity_store_id=$IDENTITY_STORE_ID and instance_arn=$INSTANCE_ARN in SSM"
