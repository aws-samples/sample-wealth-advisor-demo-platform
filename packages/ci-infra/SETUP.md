# CI/CD Setup

## 1. Prerequisites

- AWS account access with CDK bootstrapped in `us-west-2`
- GitLab project on `gitlab.aws.dev`
- `main` branch **must** be protected with required MR approvals — the IAM trust policy enforces `ProtectedBranch=Yes` and deployments will fail without this
- Node >= 22, pnpm >= 10, UV >= 0.5.29

## 2. Deploy CI Infrastructure

One-time bootstrap:

```sh
pnpm nx deploy @wealth-management-portal/ci-infra
```

Note the stack outputs:

| Output                  | Used For                          |
| ----------------------- | --------------------------------- |
| `GitLabTriggerRoleArn`  | GitLab OIDC role assumption       |
| `SourceBucketName`      | S3 bucket for source artifacts    |
| `CodeBuildProjectName`  | CodeBuild project for deployments |

## 3. Configure GitLab

In your GitLab project under **Settings → CI/CD → Variables**, add:

| Variable                | Value                                      | Notes                          |
| ----------------------- | ------------------------------------------ | ------------------------------ |
| `AWS_CREDS_TARGET_ROLE` | `GitLabTriggerRoleArn` from stack outputs  | Required for credential vendor |
| `AWS_DEFAULT_REGION`    | `us-west-2`                                | AWS region for all API calls   |
| `SOURCE_BUCKET`         | `SourceBucketName` from stack outputs      | S3 bucket for source artifacts |
| `CODEBUILD_PROJECT`     | `CodeBuildProjectName` from stack outputs  | CodeBuild project name         |

These are referenced in `.gitlab-ci.yml`.

## 4. Test the Pipeline

1. Push a feature branch and open an MR — verify lint and test jobs run
2. Merge to `main` — verify the deploy job triggers CodeBuild
3. Check the CodeBuild console in `us-west-2` for build status

## 5. Clean Up Test Stacks

```sh
pnpm nx run @wealth-management-portal/infra:destroy-ci-test
```

Tears down any `ci-test` stacks created during pipeline runs.

## 6. Teardown CI Infrastructure

```sh
pnpm nx destroy @wealth-management-portal/ci-infra
```

Removes the CI S3 bucket, CodeBuild project, and IAM roles.
