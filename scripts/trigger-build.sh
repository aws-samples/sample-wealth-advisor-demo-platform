#!/usr/bin/env bash
set -euo pipefail

# Triggers a CodeBuild build and polls until completion.
# Usage: ./scripts/trigger-build.sh <project-name> <buildspec-file>

PROJECT_NAME="${1:?Usage: $0 <project-name> <buildspec-file>}"
BUILDSPEC="${2:?Usage: $0 <project-name> <buildspec-file>}"
REGION="${AWS_REGION:-us-west-2}"

echo "🚀 Starting build: $PROJECT_NAME (buildspec: $BUILDSPEC)"
BUILD_OUTPUT=$(aws codebuild start-build \
  --project-name "$PROJECT_NAME" \
  --buildspec-override "$BUILDSPEC" \
  --region "$REGION")

BUILD_ID=$(echo "$BUILD_OUTPUT" | grep -o '"id": "[^"]*"' | head -1 | cut -d'"' -f4)
echo "   Build ID: $BUILD_ID"
echo "   Console:  https://console.aws.amazon.com/codesuite/codebuild/projects/$PROJECT_NAME/build/$BUILD_ID?region=$REGION"
echo ""

while true; do
  STATUS=$(aws codebuild batch-get-builds --ids "$BUILD_ID" --region "$REGION" \
    --query 'builds[0].buildStatus' --output text)
  PHASE=$(aws codebuild batch-get-builds --ids "$BUILD_ID" --region "$REGION" \
    --query 'builds[0].currentPhase' --output text)
  echo "$(date +%H:%M:%S) [$PHASE] $STATUS"
  case "$STATUS" in
    SUCCEEDED) echo "✓ Build succeeded"; exit 0 ;;
    FAILED|STOPPED|FAULT|TIMED_OUT) echo "✗ Build $STATUS"; exit 1 ;;
    *) sleep 10 ;;
  esac
done
