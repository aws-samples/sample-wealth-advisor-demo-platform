# infra

AWS CDK infrastructure for the wealth management portal. Defines all cloud resources — APIs, agents, gateways, databases, schedulers, and the optional bastion host — as three CDK stacks composed into a single deployment stage. Configuration is driven entirely from a root `.env` file; `cdk.json` contains only CDK feature flags.

## Architecture

The CDK app creates an `ApplicationStage` containing up to three stacks:

```
main.ts
  └─ ApplicationStage (wealth-management-portal-infra-{stageName})
       ├─ ApplicationStack ─────────────────────────────────────────────
       │    ├─ Identity (Cognito User Pool + Identity Pool)
       │    │
       │    ├─ APIs
       │    │    ├─ Api              (dashboard, clients, holdings, reports)
       │    │    ├─ IntelligenceApi  (chat — heavy AI/ML, isolated)
       │    │    └─ GraphSearchApi   (graph data load + AI search SSE)
       │    │
       │    ├─ Gateways (AgentCore Gateway — Lambda behind Gateway URL)
       │    │    ├─ PortfolioDataGateway    (Redshift via VPC)
       │    │    ├─ SmartChatDataAccess     (execute_sql for advisor chat)
       │    │    ├─ NeptuneAnalyticsGateway (Cypher queries)
       │    │    ├─ SchedulerGateway        (schedule CRUD)
       │    │    └─ EmailSenderGateway      (SES email delivery)
       │    │
       │    ├─ MCP Servers (AgentCore Runtime)
       │    │    ├─ RedshiftDataAccess  (execute_sql MCP)
       │    │    └─ WebCrawlerMcp       (web crawl + article storage)
       │    │
       │    ├─ Agents (AgentCore Runtime — Strands-based)
       │    │    ├─ RoutingAgent        (orchestrator, Cognito JWT auth)
       │    │    ├─ DatabaseAgent       (portfolio, holdings, AUM)
       │    │    ├─ StockDataAgent      (quotes, fees, dashboard)
       │    │    ├─ WebSearchAgent      (news, market themes)
       │    │    ├─ ClientSearchAgent   (NL-to-SQL)
       │    │    ├─ GraphSearchAgent    (Cypher gen + reasoning)
       │    │    ├─ ReportAgent         (PDF report generation)
       │    │    └─ VoiceGateway        (Nova Sonic speech-to-speech)
       │    │
       │    ├─ Scheduler
       │    │    ├─ SchedulesTable / ScheduleResultsTable (DynamoDB)
       │    │    ├─ ScheduleExecutor Lambda (EventBridge → routing agent)
       │    │    ├─ ReportSchedulerStateMachine (Step Functions)
       │    │    └─ ThemeGeneratorStateMachine  (Step Functions)
       │    │
       │    ├─ Scheduler Lambda Functions
       │    │    ├─ GetClientList             (Redshift client query)
       │    │    ├─ GenerateReport            (invoke report agent)
       │    │    ├─ GenerateGeneralThemes     (web crawler → themes)
       │    │    └─ GeneratePortfolioThemes   (per-client themes)
       │    │
       │    ├─ UI (React static website)
       │    │
       │    └─ EventBridge Schedules
       │         ├─ ReportSchedule  (daily 2 AM UTC, disabled)
       │         └─ ThemeSchedule   (daily 2 AM UTC, disabled)
       │
       ├─ BastionStack (optional — deployBastion=true) ─────────────────
       │    ├─ EC2 instance (t4g.nano, AL2023 ARM64, private subnet)
       │    ├─ SSM Session Manager (VPC endpoints for connectivity)
       │    ├─ Automated patching (weekly, AL2023 patch baseline)
       │    ├─ Inventory collection (12-hour SSM association)
       │    └─ Compliance reporting (optional S3 sync)
       │
       └─ RumStack (deployed manually — CloudWatch RUM app monitor) ───
```

A standalone `bastion-only.ts` entry point exists for deploying the bastion stack independently.

## File Structure

```
packages/infra/
├── src/
│   ├── main.ts                          # CDK app entry — loads .env, maps to context
│   ├── bastion-only.ts                  # Standalone bastion deployment entry
│   ├── stages/
│   │   └── application-stage.ts         # Composes Application + optional Bastion stacks
│   └── stacks/
│       ├── application-stack.ts         # All application resources (~600 lines)
│       ├── bastion-stack.ts             # EC2 bastion + SSM + patching + compliance
│       └── rum-stack.ts                 # CloudWatch RUM app monitor
├── cdk.json                             # CDK feature flags only (no account-specific values)
├── cdk.context.json                     # CDK-managed context cache (auto-generated)
├── checkov.yml                          # Checkov skip rules + output config
├── project.json                         # Nx targets (build, deploy, synth, checkov, etc.)
├── vitest.config.mts                    # Vitest config (passWithNoTests — no tests yet)
├── vite.config.mts                      # Vite config
├── eslint.config.mjs                    # ESLint config
├── tsconfig.json                        # Root TS config
├── tsconfig.lib.json                    # Library TS config (compile target)
└── tsconfig.spec.json                   # Test TS config
```

Constructs used by the stacks are defined in `packages/common/constructs/` and imported via the `:wealth-management-portal/common-constructs` path alias.

## Testing

The infra package is configured for Vitest with `passWithNoTests: true` — there are no snapshot or unit tests currently. The build pipeline runs `synth` + `checkov` as the primary validation:

```bash
# Compile TypeScript
pnpm nx compile @wealth-management-portal/infra

# Synthesize CloudFormation templates
pnpm nx synth @wealth-management-portal/infra

# Run Checkov security scan on synthesized templates
pnpm nx checkov @wealth-management-portal/infra

# Full build (lint → compile → test → synth → checkov)
pnpm nx build @wealth-management-portal/infra
```

## Deploying

```bash
# Bootstrap CDK (first time only)
pnpm nx bootstrap @wealth-management-portal/infra

# Deploy all stacks
pnpm nx deploy @wealth-management-portal/infra

# Hotswap deploy (dev only — Lambda, Step Functions, ECS)
pnpm nx deploy @wealth-management-portal/infra --hotswap --all

# Destroy all stacks
pnpm nx destroy @wealth-management-portal/infra
```

CI variants (`deploy-ci`, `destroy-ci`) use pre-synthesized templates from `dist/packages/infra/cdk.out`.

## Configuration

All configuration is driven from the root `.env` file. `main.ts` loads it via `dotenv` and maps env vars to CDK context — stacks continue using `tryGetContext()` internally.

| Variable                       | Default                | Description                                          |
|--------------------------------|------------------------|------------------------------------------------------|
| `AWS_REGION`                   | (required)             | AWS region for all resources                         |
| `STAGE_NAME`                   | `sandbox`              | CDK stage name suffix                                |
| `REDSHIFT_WORKGROUP`           | `financial-advisor-wg` | Redshift Serverless workgroup                        |
| `REDSHIFT_DATABASE`            | `financial-advisor-db` | Redshift database name                               |
| `REDSHIFT_VPC_ID`              | (required)             | VPC where Redshift is deployed                       |
| `PRIVATE_SUBNET_IDS`           | (required)             | Comma-separated private subnet IDs                   |
| `REDSHIFT_SECURITY_GROUP_ID`   | (required)             | Security group attached to Redshift                  |
| `PRIVATE_ROUTE_TABLE_ID`       | (required)             | Route table for private subnets                      |
| `TAVILY_API_KEY`               | (optional)             | Tavily API key for web search agents                 |
| `SES_SENDER_EMAIL`             | `noreply@example.com`  | SES-verified sender email                            |
| `REPORT_BEDROCK_MODEL_ID`      | (optional)             | Bedrock model for report generation                  |
| `THEME_BEDROCK_MODEL_ID`       | (optional)             | Bedrock model for theme generation                   |
| `DEPLOY_BASTION`               | `false`                | Deploy the bastion stack                             |
| `PRIVATE_SUBNET_AZ`            | (bastion only)         | AZ for bastion instance placement                    |
| `ENABLE_COMPLIANCE_REPORTING`  | `false`                | Enable SSM inventory sync to S3                      |
| `COMPLIANCE_REPORTING_BUCKET`  | (compliance only)      | S3 bucket pattern (`{region}` placeholder supported) |

Run `pnpm nx setup` from the repo root to generate `.env` interactively.

## Checkov Suppressions

Defined in `checkov.yml` — these Lambda-level checks are skipped globally:

| Rule        | Description                          | Reason                                    |
|-------------|--------------------------------------|-------------------------------------------|
| CKV_AWS_115 | Concurrent execution limit           | Not required for this workload            |
| CKV_AWS_116 | Dead Letter Queue                    | Handled at application level              |
| CKV_AWS_117 | Lambda functions in VPC              | Only data-access Lambdas need VPC         |
| CKV_AWS_173 | Encrypt Lambda environment variables | No secrets in env vars (ARNs/URLs only)   |
| CKV_AWS_272 | Code signing                         | Not required for internal deployment      |

Per-resource suppressions use `suppressRules()` from `common-constructs` (e.g. SSM patch APIs that don't support resource-level permissions).

## Dependencies

Defined in the workspace `package.json` and `tsconfig.base.json`:

- `aws-cdk-lib` — CDK core library
- `@aws-cdk/aws-bedrock-agentcore-alpha` — AgentCore Runtime constructs
- `constructs` — CDK construct base class
- `:wealth-management-portal/common-constructs` — shared application constructs (agents, gateways, APIs, Lambda functions, DynamoDB tables, Step Functions, static websites)
- `dotenv` — loads `.env` into `process.env` for CDK context mapping
- `tsx` — TypeScript execution for the CDK app entry point

## References

- [AWS CDK Developer Guide](https://docs.aws.amazon.com/cdk/v2/guide/home.html) — CDK concepts, constructs, and deployment
- [Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html) — AgentCore Runtime and Gateway
- [Checkov](https://www.checkov.io/1.Welcome/What%20is%20Checkov.html) — static analysis for CloudFormation security
- [Nx Plugin for AWS — TypeScript Infrastructure](https://awslabs.github.io/nx-plugin-for-aws/en/guides/typescript-infrastructure/) — Nx targets and project structure
