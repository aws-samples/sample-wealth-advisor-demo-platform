"""Unit tests configuration — force test env vars before nx-loaded .env values take effect."""

import os

# Force test values regardless of what nx loaded from root .env
os.environ["SCHEDULES_TABLE_NAME"] = "test-schedules"
os.environ["SCHEDULE_RESULTS_TABLE_NAME"] = "test-results"
os.environ["ROUTING_AGENT_ARN"] = "arn:aws:bedrock-agentcore:us-east-1:123456789012:agent-runtime/test-agent"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["AWS_ACCOUNT_ID"] = "123456789012"
