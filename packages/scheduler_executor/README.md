# scheduler_executor

Thin orchestrator Lambda triggered by EventBridge Scheduler at user-defined times. Reads the schedule definition from DynamoDB, invokes the routing agent on Bedrock AgentCore Runtime with an augmented message, and records the execution result. Does not execute tasks or deliver results itself — the routing agent handles delegation to specialist agents and email delivery.

[Get full details for scheduler MCP](../scheduler_MCP/README.md)

## Architecture

```
EventBridge Scheduler
       │
  (fires at cron time, passes schedule_id)
       │
       ▼
Executor Lambda
       │
       ├── 1. Read schedule from DynamoDB (Schedules table)
       │
       ├── 2. Obtain Cognito service token (client_credentials grant)
       │
       ├── 3. Invoke routing agent via AgentCore Runtime (raw HTTPS)
       │       POST /runtimes/{arn}/invocations
       │       Authorization: Bearer <service_token>
       │       X-Amzn-Bedrock-AgentCore-Runtime-Custom-UserId: {user_id}
       │
       ├── 4a. Success → update schedule last_run + write result
       │
       └── 4b. Failure → update schedule last_run + write failed result
                          (no re-raise — avoids duplicate retries)
```

The augmented message sent to the routing agent embeds the task and delivery instructions:

```
[Scheduled Task: {name}]
Task: {task_message}
Deliver results via email to: {email}
```

The routing agent parses this, delegates to the appropriate specialist agent, and calls the `send_email` MCP tool with the embedded email address.

## File Structure

```
wealth_management_portal_scheduler_executor/
├── __init__.py
└── lambda_functions/
    └── schedule_executor.py     # Lambda handler + all helper functions

tests/
├── conftest.py                  # Force test env vars before .env loads
├── unit/
│   └── test_schedule_executor.py    # 5 tests — moto DynamoDB, mocked agent
└── integration/
    ├── conftest.py              # Loads root .env, sets AWS_DEFAULT_REGION
    └── test_schedule_executor.py    # Real DynamoDB, mocked agent
```

## Testing

Unit tests use `moto` for DynamoDB and `monkeypatch` for the agent invocation — no AWS resources required:

```bash
# Run unit tests (default — integration tests excluded via pyproject.toml)
uv run pytest tests/
```

Integration tests require real DynamoDB tables and valid AWS credentials:

```bash
# Run integration tests only
uv run pytest tests/integration/ -m integration
```

Via Nx:

```bash
# Unit tests (default target)
pnpm nx test wealth_management_portal.scheduler_executor

# Lint + format
pnpm nx lint wealth_management_portal.scheduler_executor
```

## Configuration

Set via environment variables (injected by CDK in `application-stack.ts`):

| Variable                    | Description                                          |
|-----------------------------|------------------------------------------------------|
| `SCHEDULES_TABLE_NAME`      | DynamoDB table storing schedule definitions           |
| `SCHEDULE_RESULTS_TABLE_NAME` | DynamoDB table storing execution results            |
| `ROUTING_AGENT_ARN`        | AgentCore Runtime ARN for the routing agent           |
| `AWS_REGION_NAME`           | AWS region for AgentCore Runtime endpoint             |
| `EXECUTOR_CLIENT_ID`       | Cognito app client ID for client_credentials grant    |
| `EXECUTOR_CLIENT_SECRET_ARN` | Secrets Manager ARN holding the Cognito client secret |
| `COGNITO_TOKEN_ENDPOINT`   | Cognito token endpoint URL for OAuth2 token exchange  |

## Dependencies

Defined in `pyproject.toml`:

- `aws-lambda-powertools==3.24.0` — structured logging, metrics, and tracing
- `boto3>=1.34.0` — DynamoDB and Secrets Manager access

`urllib3` (bundled with Lambda runtime) is used for raw HTTPS calls to AgentCore Runtime and the Cognito token endpoint.

Dev/test dependencies:

- `moto[dynamodb]>=5.0.0` — DynamoDB mocking for unit tests
- `python-dotenv>=1.1.0` — `.env` loading for integration tests

## References

- [Lambda Powertools for Python](https://docs.powertools.aws.dev/lambda/python/latest/) — Logger, Metrics, Tracer used by the handler
- [EventBridge Scheduler](https://docs.aws.amazon.com/scheduler/latest/UserGuide/what-is-scheduler.html) — triggers this Lambda on user-defined cron schedules
- [Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html) — hosts the routing agent invoked by the executor
- [Nx Plugin for AWS — Python projects](https://awslabs.github.io/nx-plugin-for-aws/en/guides/python-project/) — build, test, and lint targets used by this package
