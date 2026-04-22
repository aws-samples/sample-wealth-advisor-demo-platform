# scheduler_mcp

MCP server for the scheduler feature. Exposes four tools — create, list, delete, and toggle schedules — behind a Bedrock AgentCore Gateway. The routing agent calls these tools when users request recurring tasks via natural language in the advisor chat. Schedules are persisted in DynamoDB and backed by EventBridge Scheduler for time-based execution.

## Architecture

```
Routing Agent (advisor chat)
        │
        ▼
AgentCore Gateway (IAM auth)
        │
        ▼
Scheduler MCP Lambda
        │
        ├── validator.py ──────── Validates cron/rate expressions
        ├── repository.py ─────── DynamoDB CRUD (Schedules + Results tables)
        └── eventbridge.py ────── EventBridge Scheduler CRUD
                                        │
                                  (fires at scheduled time)
                                        │
                                        ▼
                                  Executor Lambda
                                  (separate package — scheduler_executor)
```

The Lambda handler dispatches incoming tool calls by extracting the tool name from `context.client_context.custom["bedrockAgentCoreToolName"]` and routing to the matching handler function. On `create_schedule`, it validates the cron expression, writes to DynamoDB, then creates an EventBridge schedule targeting the executor Lambda. If EventBridge creation fails, the DynamoDB record is rolled back.

## Tool Schema

Defined in `tool-schema.json` (plain JSON array format required by AgentCore Gateway):

| Tool              | Description                                    | Required Params                                                  |
|-------------------|------------------------------------------------|------------------------------------------------------------------|
| `create_schedule` | Create a recurring schedule                    | `cron_expression`, `task_message`, `name`, `user_id`, `email`    |
| `list_schedules`  | List all schedules for a user                  | `user_id`                                                        |
| `delete_schedule` | Delete a schedule and its EventBridge schedule | `schedule_id`, `user_id`                                         |
| `toggle_schedule` | Enable or disable a schedule                   | `schedule_id`, `user_id`, `enabled`                              |

## File Structure

```
wealth_management_portal_scheduler_mcp/
├── __init__.py
├── validator.py                     # EventBridge cron/rate expression validation + normalization
├── repository.py                    # DynamoDB operations for Schedules and Schedule Results tables
├── eventbridge.py                   # EventBridge Scheduler create/delete/update
└── lambda_functions/
    └── scheduler_gateway.py         # Lambda handler — tool dispatch, Powertools instrumentation

tool-schema.json                     # MCP tool definitions (plain JSON array)

tests/
├── conftest.py                      # Sets AWS_ACCOUNT_ID for unit tests
├── test_scheduler_gateway.py        # Stub — unit tests are in tests/unit/
├── unit/
│   ├── test_scheduler_gateway.py    # Handler dispatch, create/list/delete/toggle, auth checks
│   ├── test_repository.py           # DynamoDB CRUD via moto mock
│   ├── test_eventbridge.py          # EventBridge calls via mock boto3 client
│   └── test_validator.py            # Cron/rate validation and edge cases
└── integration/
    ├── conftest.py                  # Loads root .env, sets AWS_DEFAULT_REGION
    ├── test_scheduler_gateway.py    # Full handler cycle against real DynamoDB + EventBridge
    ├── test_repository.py           # CRUD cycle against real DynamoDB
    └── test_eventbridge.py          # Schedule lifecycle against real EventBridge Scheduler
```

## Testing

Unit tests use moto (DynamoDB) and unittest.mock (EventBridge, handler dependencies):

```bash
# Run unit tests (default — integration tests excluded via pyproject.toml)
uv run pytest tests/
```

Integration tests require deployed AWS resources (DynamoDB tables, EventBridge role, executor Lambda):

```bash
# Load env vars from root .env, then run integration tests
source ../../.env
uv run pytest tests/integration/ -m integration
```

Via Nx:

```bash
# Unit tests (default target)
pnpm nx test wealth_management_portal.scheduler_mcp

# Lint + format
pnpm nx lint wealth_management_portal.scheduler_mcp
```

## Configuration

Set via environment variables or root `.env` file (loaded by integration test conftest):

| Variable                      | Description                                          |
|-------------------------------|------------------------------------------------------|
| `SCHEDULES_TABLE_NAME`        | DynamoDB table for schedule records                  |
| `SCHEDULE_RESULTS_TABLE_NAME` | DynamoDB table for execution results (TTL-enabled)   |
| `EXECUTOR_LAMBDA_ARN`         | ARN of the executor Lambda (EventBridge target)      |
| `EVENTBRIDGE_ROLE_ARN`        | IAM role ARN for EventBridge to invoke executor      |
| `AWS_DEFAULT_REGION`          | AWS region (boto3 requires this, not `AWS_REGION`)   |
| `AWS_ACCOUNT_ID`              | AWS account ID (set in unit test conftest)            |

## Dependencies

Defined in `pyproject.toml`:

- `aws-lambda-powertools==3.24.0` (with `tracer` and `parser` extras) — logging, metrics, tracing
- `boto3>=1.34.0` — DynamoDB and EventBridge Scheduler operations

Dev/test dependencies:

- `moto[dynamodb,scheduler]>=5.0.0` — AWS service mocks for unit tests
- `python-dotenv>=1.1.0` — loads `.env` for integration tests

## References

- [EventBridge Scheduler](https://docs.aws.amazon.com/scheduler/latest/UserGuide/what-is-scheduler.html) — cron/rate expressions and schedule management
- [DynamoDB single-table design](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-general-nosql-design.html) — PK/SK/GSI pattern used by the repository
- [Lambda Powertools for Python](https://docs.powertools.aws.dev/lambda/python/latest/) — structured logging, metrics, and tracing
- [Nx Plugin for AWS — Python projects](https://awslabs.github.io/nx-plugin-for-aws/en/guides/python-project/) — build, test, and lint targets used by this package
