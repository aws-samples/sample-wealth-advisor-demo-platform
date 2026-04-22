#!/usr/bin/env bash
set -e

REGION="$1"

get_status() {
  aws sso-admin list-instances --region "$REGION" --output json 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin)
instances=d.get('Instances',[])
print(instances[0]['Status'] if instances else 'NONE')
"
}

STATUS=$(get_status)

if [ "$STATUS" = "ACTIVE" ]; then
  echo "Identity Center instance already exists and is ACTIVE"
  exit 0
fi

echo "Creating Identity Center instance..."
aws sso-admin create-instance --region "$REGION" 2>/dev/null || true

echo "Waiting for Identity Center instance to become ACTIVE..."
COUNTER=0
while [ $COUNTER -lt 30 ]; do
  COUNTER=$((COUNTER + 1))
  STATUS=$(get_status)
  if [ "$STATUS" = "ACTIVE" ]; then
    echo "Identity Center instance is ACTIVE"
    exit 0
  fi
  echo "Status: $STATUS - waiting 10s (attempt $COUNTER/30)..."
  sleep 10
done

echo "ERROR: Identity Center instance did not become ACTIVE within 5 minutes"
exit 1
