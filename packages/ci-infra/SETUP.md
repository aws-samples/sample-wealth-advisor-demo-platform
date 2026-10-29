# CI/CD Setup

## 1. Prerequisites

- AWS credentials for the intended deployment account
- Node >= 22, pnpm >= 10, UV >= 0.5.29
- CDK bootstrapped in the target region
- The target account ID and region explicitly confirmed before deployment

## 2. Deploy CodeBuild Infrastructure

The `ci-infra` stack creates the S3 source bucket and the application/data-platform CodeBuild projects. It does not create an external CI trust role.

```sh
pnpm nx bootstrap @wealth-management-portal/ci-infra
pnpm nx deploy @wealth-management-portal/ci-infra
```

Record these stack outputs:

| Output                         | Used for                 |
| ------------------------------ | ------------------------ |
| `SourceBucketName`             | Source archive upload    |
| `CodeBuildProjectName`         | Application deployment   |
| `PlatformCodeBuildProjectName` | Data-platform deployment |

## 3. Deploy the Application

The helper verifies the caller account before uploading anything. It discovers the source bucket and CodeBuild project from the CI stack unless explicit overrides are supplied:

```sh
export EXPECTED_AWS_ACCOUNT_ID="<ACCOUNT_ID>"
export AWS_REGION="us-west-2"
./scripts/deploy-app.sh
```

Optional overrides:

```sh
export SOURCE_BUCKET="<source-bucket-name>"
export CODEBUILD_PROJECT="wealth-mgmt-deploy"
export CI_INFRA_STACK_NAME="wealth-management-portal-ci-infra-Ci"
```

The helper:

1. Verifies `aws sts get-caller-identity` matches `EXPECTED_AWS_ACCOUNT_ID`.
2. Runs the UI compile and lint checks.
3. Packages the repository without `.env` files, build outputs, or local caches.
4. Uploads the archive to the CI source bucket.
5. Starts CodeBuild and prints the build URL.

## 4. Validate the Deployment

Check the CodeBuild build status first. After it succeeds, retrieve the CloudFormation outputs for the application stack and run the documented API/UI smoke tests. Do not treat a successful CodeBuild submission as proof that the application is healthy.

## 5. Clean Up Test Stacks

```sh
pnpm nx run @wealth-management-portal/infra:destroy-ci-test
```

## 6. Teardown CI Infrastructure

```sh
pnpm nx destroy @wealth-management-portal/ci-infra
```

This removes the CI S3 bucket and CodeBuild projects. Use only for an explicitly identified non-production test account.
