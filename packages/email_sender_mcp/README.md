# email_sender_mcp

MCP tool gateway for sending emails via Amazon SES. Deployed as a Lambda behind Bedrock AgentCore Gateway, invoked by the routing agent to deliver task results — plain text, markdown-formatted HTML, or emails with S3 file attachments (e.g. PDF reports).

## Architecture

The Lambda receives tool invocations from the routing agent through AgentCore Gateway. It supports a single tool (`send_email`) that handles two delivery paths depending on whether an attachment is provided:

```
Routing Agent
     │
     ▼
AgentCore Gateway
     │
     ▼
Email Sender Lambda (email_sender_gateway.py)
     │
     ├── No attachment ──→ SES send_email
     │                     (HTML + plain text)
     │
     └── With attachment ─→ S3 get_object
                            │
                            ▼
                           SES send_raw_email
                           (MIME multipart: HTML + plain text + attachment)
```

- Markdown body is converted to HTML via the `markdown` library (with table extension) and styled with inline CSS for email client compatibility.
- Plain text body is always included as a fallback for clients that don't render HTML.
- Attachments are fetched from S3 by URL (`s3://bucket/key`), base64-encoded, and sent as MIME parts via `send_raw_email`.

## Tool Schema

Defined in `tool-schema.json` and registered with AgentCore Gateway:

| Parameter        | Type   | Required | Description                              |
|------------------|--------|----------|------------------------------------------|
| `to`             | string | yes      | Recipient email address                  |
| `subject`        | string | yes      | Email subject line                       |
| `body`           | string | yes      | Email body (markdown supported)          |
| `attachment_url` | string | no       | S3 URL for file attachment (`s3://...`)  |

## File Structure

```
wealth_management_portal_email_sender_mcp/
├── __init__.py
└── lambda_functions/
    └── email_sender_gateway.py   # Lambda handler, SES/S3 integration, markdown→HTML

tests/
├── conftest.py                   # Forces SES_SENDER_EMAIL for test isolation
├── unit/
│   └── test_email_sender_gateway.py  # 9 tests: send paths, MIME structure, validation, errors
└── integration/
    ├── conftest.py               # Loads root .env, sets AWS_DEFAULT_REGION
    └── test_email_sender.py      # Real SES/S3 tests (requires credentials + verified sender)
```

## Testing

Unit tests mock boto3 — no AWS credentials required:

```bash
# Run unit tests (default — integration tests excluded via pyproject.toml)
uv run pytest tests/
```

To verify a sender email in SES (required for both integration tests and production):

```bash
# Sends a verification email — click the link in your inbox to complete
./scripts/setup-ses-identity.sh user@example.com        # defaults to us-west-2
./scripts/setup-ses-identity.sh user@example.com us-east-1  # explicit region
```

Integration tests require a verified SES sender and optionally an S3 bucket:

```bash
# Set required env vars
export SES_SENDER_EMAIL=verified@example.com
export TEST_RECIPIENT_EMAIL=recipient@example.com  # defaults to SES_SENDER_EMAIL
export TEST_S3_BUCKET=my-test-bucket               # required for attachment test

# Run integration tests
uv run pytest tests/integration/ -m integration
```

Via Nx:

```bash
# Unit tests (default target)
pnpm nx test wealth_management_portal.email_sender_mcp

# Lint + format
pnpm nx lint wealth_management_portal.email_sender_mcp
```

## Configuration

| Variable                       | Default | Description                                    |
|--------------------------------|---------|------------------------------------------------|
| `SES_SENDER_EMAIL`            | (required) | Verified SES sender address                 |
| `POWERTOOLS_METRICS_NAMESPACE` | `EmailSenderGateway` | CloudWatch metrics namespace       |
| `POWERTOOLS_SERVICE_NAME`      | `EmailSenderGateway` | Powertools service name            |

The Lambda also needs IAM permissions for `ses:SendEmail`, `ses:SendRawEmail`, and `s3:GetObject` on the report bucket (granted via CDK in `application-stack.ts`).

## Dependencies

Defined in `pyproject.toml`:

- `aws-lambda-powertools==3.24.0` — logging, metrics, tracing
- `boto3>=1.34.0` — SES and S3 clients
- `markdown>=3.7` — markdown-to-HTML conversion (with `tables` extension)

Dev/test dependencies:

- `moto[s3,ses]>=5.0.0` — AWS service mocking
- `python-dotenv>=1.1.0` — `.env` loading for integration tests

## References

- [Amazon SES Developer Guide](https://docs.aws.amazon.com/ses/latest/dg/Welcome.html) — email sending, verified identities, sandbox mode
- [AWS Lambda Powertools for Python](https://docs.powertools.aws.dev/lambda/python/latest/) — structured logging, metrics, tracing
- [Python-Markdown](https://python-markdown.github.io/) — markdown-to-HTML conversion library
- [Nx Plugin for AWS — Python projects](https://awslabs.github.io/nx-plugin-for-aws/en/guides/python-project/) — build, test, and lint targets
