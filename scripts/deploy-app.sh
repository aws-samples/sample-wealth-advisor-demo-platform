#!/usr/bin/env bash
# Local helper: lint-check, package, upload to S3, and trigger wealth-mgmt-deploy.
# Run from the repo root. Requires AWS credentials (isengardcli or profile default).
set -euo pipefail

AWS_REGION="${AWS_REGION:-${CDK_DEFAULT_REGION:-us-west-2}}"
REGION_CB="${REGION_CB:-$AWS_REGION}"
REGION_S3="${REGION_S3:-$REGION_CB}"
CI_INFRA_STACK_NAME="${CI_INFRA_STACK_NAME:-wealth-management-portal-ci-infra-Ci}"
STAGE_NAME="${STAGE_NAME:-uswest2}"
EXPECTED_AWS_ACCOUNT_ID="${EXPECTED_AWS_ACCOUNT_ID:?Set EXPECTED_AWS_ACCOUNT_ID to the intended 12-digit AWS account before deploying}"
ZIP="${DEPLOY_ZIP:-/tmp/wealth-mgmt-source.zip}"

ACTUAL_AWS_ACCOUNT_ID=$(aws sts get-caller-identity \
  --query Account --output text --region "$REGION_CB")
if [[ "$ACTUAL_AWS_ACCOUNT_ID" != "$EXPECTED_AWS_ACCOUNT_ID" ]]; then
  echo "ERROR: AWS account mismatch. Expected $EXPECTED_AWS_ACCOUNT_ID, got $ACTUAL_AWS_ACCOUNT_ID." >&2
  exit 1
fi

BUCKET="${SOURCE_BUCKET:-$(aws cloudformation describe-stacks \
  --stack-name "$CI_INFRA_STACK_NAME" \
  --region "$REGION_CB" \
  --query 'Stacks[0].Outputs[?OutputKey==`SourceBucketName`].OutputValue | [0]' \
  --output text)}"
PROJECT="${CODEBUILD_PROJECT:-$(aws cloudformation describe-stacks \
  --stack-name "$CI_INFRA_STACK_NAME" \
  --region "$REGION_CB" \
  --query 'Stacks[0].Outputs[?OutputKey==`CodeBuildProjectName`].OutputValue | [0]' \
  --output text)}"

if [[ -z "$BUCKET" || "$BUCKET" == "None" || -z "$PROJECT" || "$PROJECT" == "None" ]]; then
  echo "ERROR: Could not resolve SOURCE_BUCKET/CODEBUILD_PROJECT from $CI_INFRA_STACK_NAME." >&2
  echo "Set SOURCE_BUCKET and CODEBUILD_PROJECT explicitly or deploy ci-infra first." >&2
  exit 1
fi

echo "==> Running UI compile + lint (fast CI pre-check)..."
pnpm nx run @wealth-management-portal/ui:compile
pnpm nx run @wealth-management-portal/ui:lint

echo "==> Packaging tracked source files..."
rm -f "$ZIP"
REPO_ROOT="$(git rev-parse --show-toplevel)"
(cd "$REPO_ROOT" && git ls-files -z | xargs -0 zip -q "$ZIP")
echo "    $(du -sh "$ZIP" | cut -f1)"

echo "==> Uploading to S3..."
aws s3 cp "$ZIP" "s3://$BUCKET/source.zip" --region "$REGION_S3"

echo "==> Starting CodeBuild..."
BUILD_ID=$(aws codebuild start-build \
  --project-name "$PROJECT" \
  --region "$REGION_CB" \
  --environment-variables-override "name=STAGE_NAME,value=$STAGE_NAME,type=PLAINTEXT" \
  --query 'build.id' --output text)

SHORT_ID="${BUILD_ID##*:}"
echo ""
echo "Build started: $BUILD_ID"
echo "Console: https://${REGION_CB}.console.aws.amazon.com/codesuite/codebuild/projects/${PROJECT}/build/${PROJECT}%3A${SHORT_ID}/log"
