# ci-infra

CodeBuild deployment infrastructure for the Wealth Management Portal. This package provisions an S3 source bucket and two CodeBuild projects: one for the application and one for the data platform. Deployment is triggered by the repository's parameterized local helper or a future GitHub OIDC workflow; no external CI trust role is required.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Direct deployment helper / GitHub OIDC workflow                 │
│                                                                  │
│  check stage          deploy stage (manual, main only)           │
│  ┌──────────────┐     ┌──────────────────────────────────────┐   │
│  │ lint          │     │ 1. zip source → S3 bucket            │   │
│  │ test          │     │ 2. start-build → CodeBuild           │   │
│  │ compile       │     │ 3. poll until SUCCEEDED / FAILED     │   │
│  └──────────────┘     └──────────────┬───────────────────────┘   │
└──────────────────────────────────────┼───────────────────────────┘
                                       │ uses verified AWS credentials
                                       ▼
┌──────────────────────────────────────────────────────────────────┐
│  AWS (provisioned by this package)                               │
│                                                                  │
│  ┌────────────────┐    ┌─────────────────────────────────────┐   │
│  │ S3 Bucket      │───▶│ CodeBuild (wealth-mgmt-deploy)      │   │
│  │ (source.zip)   │    │                                     │   │
│  │ 7-day expiry   │    │  buildspec.yml:                     │   │
│  └────────────────┘    │   install: node 22, pnpm, uv        │   │
│                        │   build:   synth → checkov →         │   │
│  ┌────────────────┐    │           cdk diff → cdk deploy     │   │
│  │ SSM Parameter  │───▶│                                     │   │
│  │ Store (config) │    └─────────────────────────────────────┘   │
│  └────────────────┘                                              │
└──────────────────────────────────────────────────────────────────┘
```

- **Direct deployment helper** — verifies the expected AWS account, uploads the source archive to the stack's S3 bucket, starts the selected CodeBuild project, and reports the build URL.
- **S3 Source Bucket** — ephemeral bucket with 7-day lifecycle expiry. Receives zipped source from the deploy job; CodeBuild reads it as build input.
- **CodeBuild Project** — ARM-based (`amazonlinux2-aarch64-standard:3.0`), 30-minute timeout, Docker-privileged. Environment variables sourced from SSM Parameter Store. Has `AdministratorAccess` for CDK deployments.
- **Checkov** — static security scanner run against synthesized CloudFormation templates. Suppressions configured in `checkov.yml`.

## File Structure

```
packages/ci-infra/
├── src/
│   ├── main.ts                # CDK app entry point — instantiates CiStage
│   ├── stacks/
│   │   └── ci-stack.ts        # S3 bucket and CodeBuild projects
│   └── stages/
│       └── ci-stage.ts        # CDK Stage wrapper around CiStack
├── buildspec.yml              # CodeBuild build phases (install → synth → checkov → deploy)
├── checkov.yml                # Checkov rule suppressions for CI resources
├── cdk.json                   # CDK app config and feature flags
├── project.json               # Nx targets (build, synth, checkov, deploy, test, etc.)
├── SETUP.md                   # Step-by-step CI/CD setup guide
├── eslint.config.mjs          # ESLint config (extends workspace base)
├── tsconfig.json              # TypeScript project references
├── tsconfig.lib.json          # Compiler options for source
├── tsconfig.spec.json         # Compiler options for tests
├── vite.config.mts            # Vite config
└── vitest.config.mts          # Vitest config (passWithNoTests — no tests yet)
```

## Pipeline Flow

1. Run the parameterized deployment helper with an explicit expected AWS account and region.
2. The helper zips the source, excluding local environment files, and uploads it to the CI S3 bucket.
3. The helper starts the selected CodeBuild project and reports the build status/URL.
4. CodeBuild installs Node 22, pnpm, and uv, then runs: `nx synth` → `checkov` → `cdk diff` → `cdk deploy`.

## Testing

No unit tests exist yet — `vitest` is configured with `passWithNoTests: true`.

```bash
# Lint
pnpm nx lint @wealth-management-portal/ci-infra

# Compile (type-check)
pnpm nx compile @wealth-management-portal/ci-infra

# Synthesize CloudFormation
pnpm nx synth @wealth-management-portal/ci-infra

# Run Checkov against synthesized templates
pnpm nx checkov @wealth-management-portal/ci-infra
```

## Deploying

```bash
# One-time CDK bootstrap (if not already done)
pnpm nx bootstrap @wealth-management-portal/ci-infra

# Deploy CI stack
pnpm nx deploy @wealth-management-portal/ci-infra

# Destroy CI stack
pnpm nx destroy @wealth-management-portal/ci-infra
```

See `SETUP.md` for the direct deployment setup and required environment variables.

## Configuration

CodeBuild environment variables are sourced from SSM Parameter Store:

| Parameter                                               | Description                                          |
| ------------------------------------------------------- | ---------------------------------------------------- |
| `/wealth-management-portal/aws-region`                  | AWS region                                           |
| `/wealth-management-portal/redshift-vpc-id`             | VPC ID for Redshift access                           |
| `/wealth-management-portal/private-subnet-ids`          | Private subnet IDs (comma-sep)                       |
| `/wealth-management-portal/redshift-security-group-id`  | Redshift security group ID                           |
| `/wealth-management-portal/private-route-table-id`      | Private route table ID                               |
| `/wealth-management-portal/redshift-workgroup`          | Redshift Serverless workgroup name                   |
| `/wealth-management-portal/redshift-database`           | Redshift database name                               |
| `/wealth-management-portal/ses-sender-email`            | SES verified sender email                            |
| `/wealth-management-portal/report-bedrock-model-id`     | Bedrock model ID for reports                         |
| `/wealth-management-portal/tavily-api-key`              | Tavily API key for web search                        |
| `/wealth-management-portal/theme-bedrock-model-id`      | Bedrock model ID for themes                          |
| `/wealth-management-portal/deploy-bastion`              | Whether to deploy bastion host                       |
| `/wealth-management-portal/private-subnet-az`           | Private subnet availability zone                     |
| `/wealth-management-portal/enable-compliance-reporting` | Enable compliance reporting                          |
| `/wealth-management-portal/compliance-reporting-bucket` | S3 bucket for compliance reports                     |
| `/wealth-management-portal/neptune-graph-id`            | Neptune graph ID (CDK-managed — do not set manually) |

The application deployment also accepts `NEPTUNE_PUBLIC_CONNECTIVITY=false`; set it to `true` only for a reviewed requirement.

The direct deployment helper accepts these environment variables:

| Variable                  | Default                                | Description                                                         |
| ------------------------- | -------------------------------------- | ------------------------------------------------------------------- |
| `EXPECTED_AWS_ACCOUNT_ID` | _(required)_                           | Account guard; deployment stops on mismatch                         |
| `AWS_REGION`              | `us-west-2`                            | Region containing the CI stack and CodeBuild project                |
| `CI_INFRA_STACK_NAME`     | `wealth-management-portal-ci-infra-Ci` | CloudFormation stack used to discover the source bucket and project |
| `SOURCE_BUCKET`           | _(discovered from stack)_              | Optional explicit source bucket override                            |
| `CODEBUILD_PROJECT`       | _(discovered from stack)_              | Optional explicit CodeBuild project override                        |

Example:

```bash
export EXPECTED_AWS_ACCOUNT_ID="<ACCOUNT_ID>"
export AWS_REGION="us-west-2"
./scripts/deploy-app.sh
```

## Dependencies

- `aws-cdk-lib` — CDK constructs (S3, CodeBuild, IAM, CfnOutput)
- `constructs` — CDK construct base class
- `tsx` — TypeScript execution for CDK app entry point

Dev dependencies: `vitest`, `vite`, `eslint`, `typescript` (managed at workspace level).

## References

- [AWS CDK TypeScript reference](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-construct-library.html) — construct library docs
- [AWS CodeBuild](https://docs.aws.amazon.com/codebuild/latest/userguide/welcome.html) — build project configuration
- [Checkov](https://www.checkov.io/1.Welcome/What%20is%20Checkov.html) — infrastructure-as-code static analysis
- [Nx Plugin for AWS — TypeScript infrastructure](https://awslabs.github.io/nx-plugin-for-aws/en/guides/typescript-infrastructure/) — build, synth, and deploy targets
