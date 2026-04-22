#!/bin/bash
# Validate the report agent end-to-end: invocation → S3 PDF → Redshift record
cd "$(dirname "$0")/.." && \
uv run --project packages/report scripts/test-report-invocation.py \
  --stack-name wealth-management-portal-infra-sandbox-Application \
  --client-id CL00007
