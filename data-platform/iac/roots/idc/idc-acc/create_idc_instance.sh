#!/usr/bin/env bash
set -e

REGION="$1"

# IAM Identity Center is account-scoped (one instance per account).
# list-instances returns the same result regardless of the --region flag used;
# any region endpoint works as a lookup.  We use the requested region first,
# then fall back to us-east-1 and us-west-2 to handle accounts where the
# instance was created in a different region.
get_active_instance() {
  for r in "$REGION" us-east-1 us-west-2 ap-southeast-2 eu-west-1; do
    STATUS=$(aws sso-admin list-instances --region "$r" --output json 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin)
instances=d.get('Instances',[])
print(instances[0]['Status'] if instances else 'NONE')
" 2>/dev/null || echo "NONE")
    if [ "$STATUS" = "ACTIVE" ]; then
      echo "ACTIVE"
      return
    fi
  done
  echo "NONE"
}

STATUS=$(get_active_instance)

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
  STATUS=$(get_active_instance)
  if [ "$STATUS" = "ACTIVE" ]; then
    echo "Identity Center instance is ACTIVE"
    exit 0
  fi
  echo "Status: $STATUS - waiting 10s (attempt $COUNTER/30)..."
  sleep 10
done

echo "ERROR: Identity Center instance did not become ACTIVE within 5 minutes"
exit 1
