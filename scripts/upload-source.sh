#!/usr/bin/env bash
set -euo pipefail

# Zips the repository and uploads it to the CI source S3 bucket.
# The bucket name is read from the ci-infra CloudFormation stack output.

STACK_NAME="wealth-management-portal-ci-infra-Ci"
REGION="${AWS_REGION:-us-west-2}"
ZIP_PATH="/tmp/wealth-mgmt-source.zip"

echo "📦 Resolving source bucket from CloudFormation stack..."
SOURCE_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='SourceBucketName'].OutputValue" \
  --output text)

if [[ -z "$SOURCE_BUCKET" || "$SOURCE_BUCKET" == "None" ]]; then
  echo "✗ Could not resolve SourceBucketName from stack $STACK_NAME" >&2
  exit 1
fi

echo "📦 Zipping repository (tracked files only)..."
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"
git ls-files -z | xargs -0 zip -q "$ZIP_PATH"

echo "☁️  Uploading to s3://$SOURCE_BUCKET/source.zip ..."
aws s3 cp "$ZIP_PATH" "s3://$SOURCE_BUCKET/source.zip" --region "$REGION"
rm -f "$ZIP_PATH"

echo "✓ Source uploaded to s3://$SOURCE_BUCKET/source.zip"
