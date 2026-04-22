# CodeBuild Dev Experience — Implementation Plan

Automate the full wealth-management-portal deployment via CodeBuild so that a developer can go from a fresh AWS account to a running application with minimal manual intervention.

## Implementation Progress

All 9 work units are **complete**. Code is written and `ci-infra` builds successfully. Next step is end-to-end installation testing.

| WU | Status | Deliverable |
|----|--------|-------------|
| WU-1 | ✅ Done | `scripts/setup-ssm-params.sh` — dual-mode SSM setup (interactive + `--ci`) |
| WU-2 | ✅ Done | `data-platform/scripts/ci-init.sh` — non-interactive platform init |
| WU-3 | ✅ Done | `data-platform/scripts/wait-glue-jobs.sh` — polls 24 Glue jobs |
| WU-4 | ✅ Done | `scripts/generate-env-from-ssm.sh` — .env from CodeBuild env vars |
| WU-5 | ✅ Done | Idempotency fixes: `Makefile.template` (3 targets) + `redshift-tables.sql` (IF NOT EXISTS) |
| WU-6 | ✅ Done | `scripts/create-user.mjs` — added `--email`/`--password` CLI args |
| WU-7 | ✅ Done | `buildspec-platform.yml` + `buildspec-app.yml` at repo root |
| WU-8 | ✅ Done | `ci-stack.ts` — added `PlatformDeployProject`, extended trigger role |
| WU-9 | ✅ Done | `README.md` — added CI/CD Deployment section |

### Post-implementation fixes

- Moved `TEST_USER_EMAIL`/`TEST_USER_PASSWORD` out of the `ci-stack.ts` project env vars and into `buildspec-app.yml`'s `env.parameter-store` section only. Reason: project-level Parameter Store vars are resolved at build start for *every* build — if those SSM params don't exist, the existing GitLab pipeline would break.

### Decisions made during installation testing

1. **Default app name changed from `advisor` to `finadv`** — `advisor` is 7 chars, exceeds the ≤6 char validation. `finadv` is 6 chars, lowercase alphanumeric.

2. **Infrastructure auto-discovery moved from `setup-ssm-params.sh` to `generate-env-from-ssm.sh`** — instead of requiring the user to run the setup script twice (once before Phase 1, once after to fill in VPC/subnet/SG/workgroup), `generate-env-from-ssm.sh` now auto-discovers these at Phase 2 build time from data-platform SSM params (`/{app}/{env}/vpc_id`, `vpc_private_subnet_ids`, `vpc-sg`, `sagemaker/producer/security-group`, `vpc_private_route_table_id`, `sagemaker/producer/redshift-env-id`). The setup script now only prompts for values that require human input.

3. **`buildspec-app.yml` simplified** — replaced 6 infrastructure SSM param-store entries with 2 platform identifiers (`APP_NAME`, `ENV_NAME`). Infrastructure is auto-discovered by `generate-env-from-ssm.sh` at build time. Reduced from 17 to 13 parameter-store entries.

4. **`ci-stack.ts` left unchanged for now** — the existing GitLab `buildspec.yml` still depends on the project-level infra env vars. Plan: after validating the new CodeBuild flow end-to-end, migrate the GitLab buildspec to also use `generate-env-from-ssm.sh`, then remove the redundant infra SSM env vars from `ci-stack.ts`.

5. **GitLab migration plan** — once CodeBuild CI/CD is validated:

6. **Source upload step was missing from the plan** — both CodeBuild projects use S3 as their source, but the plan never documented uploading the repo to S3 before triggering builds. The GitLab pipeline handles this automatically (zips and uploads in its deploy stage), but manual triggers need an explicit upload step. Created `scripts/upload-source.sh` to resolve the bucket from CloudFormation outputs, zip the repo (excluding `.git`), and upload as `source.zip`. Added as step 3 in the README CI/CD section.
   - Update `packages/ci-infra/buildspec.yml` to use `generate-env-from-ssm.sh` (same as `buildspec-app.yml`)
   - Remove infra SSM env vars (`REDSHIFT_VPC_ID`, `PRIVATE_SUBNET_IDS`, `REDSHIFT_SECURITY_GROUP_ID`, `PRIVATE_ROUTE_TABLE_ID`, `REDSHIFT_WORKGROUP`, `PRIVATE_SUBNET_AZ`) from `ci-stack.ts` project env vars
   - Remove corresponding SSM params from `setup-ssm-params.sh` (already done)

### Remaining: Installation Testing

Testing in progress. Status:

1. ✅ `ci-infra` builds successfully
2. ✅ `setup-ssm-params.sh` tested interactively — works
3. ✅ `ci-infra` deployed — both CodeBuild projects created
4. ✅ `buildspec-platform.yml` — Phase 1 build #38 **SUCCEEDED** (after fixing Issues 1–29b)
5. ✅ Complete the 1 manual console step — reset IDC passwords (Redshift grants and QuickSight dataset now automated, Issues 26–28)
6. ✅ Deploy QuickSight dataset — automated in buildspec (Issue 27)
7. ✅ `buildspec-app.yml` — Phase 2 build **SUCCEEDED** (after fixing Issues 29–31)
8. ⬜ Test idempotency — re-trigger both buildspecs in a fresh account
9. ⬜ Verify existing GitLab pipeline still works

### Issues Found and Fixed During Installation Testing

**Issue 1: No source upload step** — CodeBuild projects use S3 source but the plan never documented uploading the repo. Created `scripts/upload-source.sh` (resolves bucket from CFN output, zips tracked files via `git ls-files`, uploads as `source.zip`). Added as step 3 in README. Also created `scripts/trigger-build.sh` that starts a build and polls status every 10 seconds.

**Issue 2: S3 source path empty** — CodeBuild projects had `path: ''` which expects loose files in the bucket root, not a zip. Fixed `ci-stack.ts` to use `path: 'source.zip'`. Re-deployed ci-infra.

**Issue 3: YAML parse error in buildspec post_build** — Individual `echo` commands with colons and special characters were parsed as YAML structure. Fixed by using a single `|` multiline block for all post_build echo statements.

**Issue 4: `yum` not found** — `STANDARD_7_0` image is Ubuntu, not Amazon Linux. Switched platform project to `aws/codebuild/amazonlinux2-aarch64-standard:3.0` (same ARM AL2 image as the existing app project). Re-deployed ci-infra.

**Issue 5: `.python-version` mismatch** — Repo has `.python-version` set to `3.12.0` but CodeBuild's pyenv doesn't have that exact patch version. Fixed by overriding pyenv global to whatever 3.12.x is available before running pip.

**Issue 6: `cd` doesn't persist across CodeBuild commands** — Each `- command` in a buildspec runs in a separate shell. The `pre_build` phase `cd data-platform` persists into `build`, but individual commands within a phase don't. Fixed by using a single `|` multiline block with `set -e` for the build phase. Removed duplicate `cd data-platform` from build (already there from pre_build).

**Issue 7: `datapipeline` IAM user missing** — Makefile targets reference a `datapipeline` IAM user for Lake Formation admin. Added `aws iam create-user` + `attach-user-policy` to pre_build (idempotent with `|| true`).

**Issue 8: SSM parameters not idempotent** — VPC Terraform module's `aws_ssm_parameter` resources lack `overwrite = true`, causing failures on re-run when parameters exist outside TF state. Added `overwrite = true` to all 6 VPC SSM parameter resources.

**Issue 9: `wait-glue-jobs.sh` arithmetic bug** — `(( done_count++ ))` returns exit code 1 when `done_count` is 0 (post-increment evaluates to old value, 0 = falsy in bash). Under `set -e`, this kills the script silently. Fixed by using `done_count=$(( done_count + 1 ))` assignment form which never fails.

**Issue 10: Orphaned VPCs from failed runs** — Three duplicate `finadv-dev1-vpc` VPCs created by interrupted Terraform runs (no state file for VPC module). Hit VPC limit on re-run. Cleaned up all 3 orphaned VPCs and their resources (subnets, NAT gateways, IGWs, endpoints, SGs, route tables, EIPs). Also cleaned up orphaned MSK cluster, EC2 instance, and 6 SSM parameters.

**Issue 11: MSK module destroys and recreates on every run** — Three root causes:
  - `aws_security_group.lambda_sg`: `vpc_id` sourced from SecureString SSM param. Terraform can't compare sensitive values, falsely detects diff, forces SG replacement → 45-min ENI cleanup stall.
  - `aws_lambda_layer_version.dependencies_layer`: `source_code_hash` changes on every build because pip produces different zip metadata. Forces layer replacement.
  - `aws_instance.msk_client`: `data.aws_ami.amazon_linux_2023` with `most_recent = true` returns a different AMI as AWS publishes updates. AMI is force-new, triggers EC2 replacement.
  - Fixed all three with `lifecycle { ignore_changes }` blocks, with comments explaining why and how to force updates when genuinely needed (`terraform taint`).

**Issue 12: Terraform state surgery** — Removed `aws_security_group.lambda_sg` and `module.data_generator_lambda.aws_lambda_function.function` from MSK module state after manually deleting the Lambda to unblock stuck ENIs. State is stored in S3 (`finadv-dev1-tf-back-end-849404653027-us-west-2`), so changes from local machine apply to CodeBuild runs.

**Issue 13: Stale Terraform lock + orphaned VPCs (again)** — Build #17 was manually stopped while MSK `terraform apply` was running, leaving a stale DynamoDB lock. Build #18 succeeded through VPC creation (new VPC + NAT gateway + endpoints) but failed at MSK due to the stale lock. Build #19 then tried to create *another* VPC (VPC module state was empty — never persisted) and hit VPC/EIP quota limits. Root cause: the VPC Terraform module never successfully saved state across any build, so every build attempted a fresh VPC creation.
  - Cleared the stale lock from DynamoDB (`finadv-dev1-tf-back-end-lock`)
  - Discovered 3 orphaned `finadv-dev1-vpc` VPCs: two truly orphaned (not in any TF state), one referenced by MSK module state
  - Cleanest fix: `terraform destroy` MSK module (state was already out of sync — actual resources deleted manually), delete all 3 orphaned VPCs and their dependencies (NAT gateways, VPC endpoints, IGWs, security groups, subnets, route tables, Lambda ENIs, EC2 instances), release 4 orphaned EIPs
  - Deleted stale MSK state file from S3 so next build starts completely fresh
  - Also had to delete the corresponding MD5 digest entry from DynamoDB (`<key>-md5` suffix) — Terraform validates the S3 state checksum against the DynamoDB digest on init, and a missing state file with a present digest causes a checksum mismatch error
  - Lesson: when deleting a Terraform state file from S3, always delete the matching `-md5` digest entry from DynamoDB too. And manually stopping a build mid-`terraform apply` leaves stale locks AND can create resources that never get recorded in state.

**Issue 14: VPC module missing `backend.tf.template` — root cause of all VPC orphaning** — The VPC Terraform module had no `backend.tf.template`, and neither `ci-init.sh` nor `init.sh` included `vpc/backend.tf` in their template resolution lists. Every other module had both `backend.tf` and `terraform.tfvars` templates. Without `backend.tf`, Terraform fell back to **local state** on every CodeBuild run (ephemeral container), so VPC resources were never tracked and every build created a new VPC.
  - Created `data-platform/iac/roots/foundation/vpc/backend.tf.template` (copied pattern from other modules)
  - Added `./iac/roots/foundation/vpc/backend.tf` to template lists in both `ci-init.sh` and `init.sh`
  - Cleaned up all orphaned VPCs (5 total across Issues 10, 13, 14), orphaned EIPs, and orphaned MSK resources
  - Imported the surviving VPC into Terraform state, verified state persisted to S3
  - This was the root cause behind Issues 10 and 13 — those were symptoms of the missing backend template

**Issue 15: `create-glue-s3tables-catalog` idempotency fix broken** — The WU-5 fix used `aws glue get-catalog` to check existence before creating, but `get-catalog` doesn't exist in the AWS CLI version on CodeBuild AL2. Changed to simpler `|| true` pattern (matches existing `register-s3table-catalog-with-lake-formation` target).

**Issue 16: `lifecycle { ignore_changes = [vpc_id] }` on lambda_sg made VPC mismatch permanent** — The Issue 11 fix added `ignore_changes = [vpc_id]` to suppress false diffs from SecureString SSM params. But once the SG was created in the wrong VPC (due to stale SSM params from Issue 14), Terraform would never detect or fix the mismatch. Removed the `ignore_changes = [vpc_id]` block. The other `ignore_changes` blocks (AMI on EC2, source_code_hash on Lambda layer) are safe — they don't affect VPC placement.

**Issue 17: `wait-datazone-stacks` race condition** — The wait target queried `CREATE_IN_PROGRESS` stacks once. If child stacks hadn't been created yet (parent still setting up), the query returned nothing and the wait exited immediately. Fixed by polling every 30 seconds and requiring 3 consecutive checks with zero in-progress stacks before proceeding. Also destroyed all SageMaker/DataZone modules and their 7 CloudFormation stacks to clean up resources in the wrong VPC.

**Issue 18: DataZone project name conflict** — After destroying and recreating the SageMaker domain, old DataZone projects ("Producer", "Consumer") survived inside the domain. The Custom Resource Lambda got `ConflictException` on `CreateProject` but failed to send the FAILED response to CloudFormation (swallowed exception in `sendResponseCfn`), causing a misleading "no response received" timeout. Fixed by deleting the entire DataZone domain (`aws datazone delete-domain --skip-deletion-check`) and clearing all SageMaker Terraform state files.

**Issue 19: Lambda ENI circular dependency blocks SG replacement** — Removing `lifecycle { ignore_changes = [vpc_id] }` (Issue 16) caused Terraform to detect the VPC mismatch and plan a replace on `lambda_sg`. But the old SG couldn't be deleted because Lambda ENIs were still attached, and the Lambda couldn't be updated to the new SG because it didn't exist yet (destroy-before-create). ENIs are Lambda hyperplane-managed and can't be force-detached — they only release ~20 minutes after the Lambda function is deleted. Fixed by adding `create_before_destroy = true` and switching from `name` to `name_prefix` on `lambda_sg`, so Terraform creates the new SG first, updates the Lambda, then deletes the old one.

**Issue 20: Lambda hyperplane ENIs don't release after SG switch** — Even with `create_before_destroy`, the old `lambda_sg` can't be deleted because Lambda hyperplane ENIs (`ela-attach-*`) remain `in-use` for 30+ minutes after the Lambda is updated to the new SG. This is an AWS Lambda platform behavior — hyperplane ENIs are not released when the Lambda's VPC config changes, only when the Lambda is deleted or VPC config is fully removed. Workaround: manually remove Lambda VPC config (`aws lambda update-function-configuration --vpc-config SubnetIds=[],SecurityGroupIds=[]`) to trigger ENI release. The fundamental issue is that Terraform's SG replacement requires the old SG to be deleted, but Lambda won't release ENIs from the old SG in a timely manner.

**Issue 21: Stale DynamoDB lock from stopped build #31** — Build #31 was stopped mid-`terraform apply` on MSK module, leaving a stale lock in DynamoDB. Build #32 failed immediately with `ConditionalCheckFailedException`. Fixed by deleting the lock entry from `finadv-dev1-tf-back-end-lock`. Lesson reinforced: always clear DynamoDB locks after stopping a build mid-apply.

**Issue 22: Orphaned IAM policies + KMS aliases from MSK cleanup** — When we manually deleted MSK resources before build #33, we missed 2 IAM policies (`finadv-dev1-kafka-permissions`, `finadv-dev1-msk-producer-lambda-policy`), 2 KMS aliases (`alias/cloudwatch//aws/lambda/finadv-dev1-msk-producer-lambda`, `alias/finadv-dev1-msk-secret-key`), and 1 IAM instance profile (`finadv-dev1-msk-client-profile`). Build #33 created some resources (44 in state) but failed on the pre-existing IAM policies and KMS alias. Fixed by deleting all orphaned resources. The IAM policies and KMS aliases were NOT in the partial state file (they failed to create), so Terraform would create them fresh. Only the instance profile was in state but deleted — Terraform handles that via drift detection.

**Issue 23: SSM parameters missing `overwrite = true` across entire data-platform** — Issue 8 only fixed VPC module. Build #35 failed at `deploy-domain` (SageMaker) with `ParameterAlreadyExists` on 5 SSM parameters (`smus_domain_id`, `project_profile_1` through `project_profile_4`). Root cause: systemic — almost none of the data-platform Terraform modules had `overwrite = true`. Fixed **50 SSM parameter resources across 20 files** in `data-platform/iac/roots/` and `data-platform/iac/templates/modules/`.

**Issue 24: Orphaned `DatazoneLambdaExecutionRole` + Lambda layers** — Build #36 failed at `deploy-project-prereq` because IAM role `DatazoneLambdaExecutionRole` already existed from a previous deployment that was destroyed (Issue 18). The role and 3 Lambda layer versions (`datazone_lambda_layer` v1-3) survived the destroy because they weren't in Terraform state. Deleted all orphaned resources manually.

**Issue 25: `extract-consumer-info` querying `DELETE_COMPLETE` stacks** — Build #36 failed after deploying the consumer project because `extract-consumer-info` called `aws cloudformation list-stacks` without `--stack-status-filter`, returning 7 `DELETE_COMPLETE` DataZone stacks from a previous deployment. It then tried `describe-stacks` on each, which errors for deleted stacks. Fixed by adding `--stack-status-filter CREATE_COMPLETE` to the `list-stacks` call in `Makefile.template`, matching what `extract-producer-info` already had.

**Issue 26: CodeBuild role not a Lake Formation admin** — Build #37 succeeded overall but `grant-s3table-lakeformation-permissions` failed with `AccessDeniedException: Insufficient Glue permissions to access database financial_advisor`. The target uses `|| true` so it didn't fail the build, but the grants weren't applied. Root cause: the CodeBuild service role wasn't in the Lake Formation DataLakeAdmins list. Fixed by modifying `set-up-lake-formation-admin-role` in `Makefile.template` to dynamically add the caller's own ARN (`aws sts get-caller-identity --query Arn`) as a 4th LF admin. This runs before the grant target in the buildspec, so the caller is always an LF admin by the time grants execute. Works for both CodeBuild and manual runs.

**Issue 26b: Redshift admin GRANT step automated** — The manual "Grant Redshift access via Query Editor v2" step was automatable. Created new make target `grant-redshift-admin-access` in `Makefile.template` that discovers the admin secret ARN via Secrets Manager, gets the workgroup name from SSM, and runs all 7 SQL statements (CREATE USER + GRANTs for both `IAMR:{ADMIN_ROLE}` and `IAM:datapipeline`) via `aws redshift-data execute-statement` with polling. Added to `buildspec-platform.yml` after `deploy-redshift-ddl`. Removed from post_build manual steps. Manual steps reduced from 3 to 2.

**Issue 27: QuickSight role assignment is NOT a console-only step** — Investigation revealed that the "Assign QuickSight role" console step was a misdiagnosis. The `aws_quicksight_vpc_connection` Terraform resource already passes `role_arn` directly in the API call — it does not depend on the account-level QuickSight role setting (which is what the console step configures). Smoke test confirmed: `aws quicksight create-vpc-connection --role-arn arn:aws:iam::849404653027:role/finadv-dev1-quicksight-service-role ...` succeeded and reached `CREATION_SUCCESSFUL / AVAILABLE` status without any prior console step. Root cause of the original belief: the console step sets the *default account-level IAM role* for QuickSight's AWS resource access, but VPC connections take their own `role_arn` parameter independently. Fix: removed the QuickSight role assignment manual step, folded `make deploy-quicksight-dataset` back into `buildspec-platform.yml` after `deploy-quicksight-subscription`. No new IAM permissions needed (CodeBuild role already has `AdministratorAccess`). Manual steps reduced from 2 to 1.

**Issue 28: IDC password reset cannot be automated** — Confirmed via AWS re:Post (official AWS answer, 4 upvotes), AWS documentation, and exhaustive review of the `sso-admin` and `identitystore` CLI API references. Neither API namespace has any `ResetPassword`, `GeneratePassword`, `SendInvite`, or `SendActivationEmail` operation. The only workaround documented by AWS is the IAM Identity Center console. The "Send email OTP" setting (Settings → Authentication → Standard authentication → Send email OTP) can be enabled to auto-send a verification email on first sign-in attempt, but this is also a console-only configuration. The IDC password reset remains a manual step.

**Issue 29: `buildspec-app.yml` YAML parse error** — CodeBuild's YAML parser rejected `echo ""` (empty string) and the `\|` in grep patterns as YAML structure. Error: `Expected Commands[6] to be of string type: found subkeys instead`. Fixed by collapsing all post_build commands into a single `|` multiline block (same pattern used for `buildspec-platform.yml` in Issue 3).

**Issue 30: Project-level SSM env vars block builds when params don't exist** — `ci-stack.ts` had 8 infrastructure SSM params (`REDSHIFT_VPC_ID`, `PRIVATE_SUBNET_IDS`, `REDSHIFT_SECURITY_GROUP_ID`, `PRIVATE_ROUTE_TABLE_ID`, `REDSHIFT_WORKGROUP`, `PRIVATE_SUBNET_AZ`, `ENABLE_COMPLIANCE_REPORTING`, `COMPLIANCE_REPORTING_BUCKET`) as project-level `PARAMETER_STORE` env vars. These are resolved at build start for *every* build — if any don't exist in SSM, the build fails before even downloading source. Root cause: these were kept for backward compat with the GitLab `buildspec.yml` (Decision #4), but `generate-env-from-ssm.sh` now auto-discovers all of them. Fix: removed all 8 from `ci-stack.ts`, added `APP_NAME`/`ENV_NAME` instead (needed by `generate-env-from-ssm.sh`). Updated GitLab `buildspec.yml` to use `generate-env-from-ssm.sh` in pre_build. Compliance reporting hardcoded as `false`/empty in buildspec env vars (internal-only feature). Redeployed `ci-infra`.

**Issue 31: App project CodeBuild role not a Lake Formation admin** — Phase 2's `grant-lf-permissions` failed because the app project's CodeBuild role (`DeployProjectRole`) wasn't in the LF DataLakeAdmins list. Issue 26 only fixed this for the platform project's role. Fix: added LF admin self-registration to `buildspec-app.yml` — reads current LF admin list, converts the assumed-role ARN to IAM role ARN (same sed as Issue 29b), appends if not already present, writes back. Idempotent and doesn't clobber existing admins.

**Issue 29b: `set-up-lake-formation-admin-role` fails with assumed-role ARN** — `aws sts get-caller-identity` returns `arn:aws:sts::ACCOUNT:assumed-role/ROLE/SESSION` in CodeBuild, but Lake Formation rejects temporary credential ARNs. Fixed by piping through `sed 's|arn:aws:sts:|arn:aws:iam:|;s|:assumed-role/\([^/]*\)/.*|:role/\1|'` to convert to the IAM role ARN. Works for both assumed roles and IAM users (sed pattern doesn't match user ARNs).

**Bonus: `generate-env-from-ssm.sh` made hands-free** — Script previously required `AWS_REGION`, `APP_NAME`, `ENV_NAME` as env vars (set by CodeBuild). Now auto-resolves all three: `AWS_REGION` from `aws configure get region`, `APP_NAME`/`ENV_NAME` from SSM (`/wealth-management-portal/platform/*`). Also fetches app-level SSM params (`REDSHIFT_DATABASE`, `SES_SENDER_EMAIL`, etc.) when not in env. Users can now run `scripts/generate-env-from-ssm.sh` with zero arguments to generate a complete `.env`.

### Installation Testing — Complete ✅

**Phase 1**: Build #38 SUCCEEDED — all data-platform make targets completed, including QuickSight dataset (Issue 27). LF admin self-registration working (Issue 29b). Redshift admin grants automated (Issue 26b).

**Phase 2**: Build SUCCEEDED — CDK deploy, LF grants, Redshift grants, Neptune data load, Cognito test user creation all passed. Application smoke-tested via CloudFront URL (`dwt962s2me795.cloudfront.net`).

**What's deployed and working:**
- ✅ VPC, KMS keys, IAM roles, S3 buckets
- ✅ MSK Serverless cluster
- ✅ IAM Identity Center (users created, passwords require manual reset)
- ✅ SageMaker domain + projects (Producer + Consumer)
- ✅ Glue, Lake Formation, Athena
- ✅ Financial Advisor data lake (24 Glue jobs)
- ✅ Redshift DDL + admin grants
- ✅ QuickSight subscription + dataset + RUM tables
- ✅ CDK application (Lambda, API Gateway, Neptune, Cognito, CloudFront)
- ✅ Lake Formation grants for all application roles
- ✅ Redshift grants for all application roles
- ✅ Neptune graph data loaded
- ✅ Test user created

**Remaining manual step (1 only):**
- Reset IDC passwords — IAM Identity Center console → Users → Reset password for each user

**Total issues found and fixed during installation testing: 31** (Issues 1–31, plus 26b and 29b)

**Key improvements made during testing:**
- `generate-env-from-ssm.sh` is fully hands-free (auto-resolves region, app/env names, all config from SSM)
- Project-level SSM env vars removed from `ci-stack.ts` — both buildspecs and GitLab pipeline use `generate-env-from-ssm.sh`
- Manual steps reduced from 3 to 1 (Redshift grants automated, QuickSight role assignment was unnecessary)
- Compliance reporting decoupled from CI/CD (hardcoded off, internal-only feature)

## Current State

- **Phase 1 (data-platform)**: Deployed via `make` targets wrapping Terraform. Requires interactive `make init` (prompts for account ID, app name, env name, regions, admin role). ~10 sequential deployment stages with manual wait gates (Glue jobs, CloudFormation stacks) and console steps (IDC password resets, Redshift Query Editor grants, QuickSight role assignment).
- **Phase 2 (application)**: Deployed via CDK. Requires interactive `pnpm nx setup` (generates `.env` from prompts), then `pnpm nx deploy`. Post-deploy steps: Lake Formation grants, Redshift grants, Cognito user creation, Neptune data load.
- **Existing CI**: `packages/ci-infra` has a CodeBuild project (`wealth-mgmt-deploy`) that runs Phase 2 only — synth, checkov, diff, deploy. Reads config from SSM parameters. Triggered via GitLab.

## Design Decision: Two Buildspecs

A single buildspec would exceed CodeBuild's 8-hour timeout and conflate unrelated failure domains. Splitting into two gives:

- **Independent re-runnability** — re-run Phase 1 without touching Phase 2 and vice versa
- **Separation of concerns** — Terraform vs CDK, different IAM requirements
- **Shorter feedback loops** — Phase 2 runs in ~15 min; Phase 1 takes 1–2 hours

## Architecture

```
Developer
  │
  ├─ 1. Fills SSM parameters (one-time, via setup script or manually)
  │
  ├─ 2. Uploads source to S3 (scripts/upload-source.sh)
  │
  ├─ 3. Triggers buildspec-platform.yml  ──▶  CodeBuild (Phase 1)
  │     └─ Deploys data-platform via Terraform make targets
  │     └─ Prints manual step in build output
  │
  ├─ 4. Manual console step (IDC passwords)
  │
  └─ 5. Triggers buildspec-app.yml       ──▶  CodeBuild (Phase 2)
        └─ Generates .env from SSM
        └─ CDK deploy + post-deploy steps
```

## Configuration Strategy

Both buildspecs read all configuration from SSM Parameter Store — no interactive prompts, no `.env` files checked in.

### SSM Parameters (pre-populated by developer)

**Platform parameters** (new — needed by Phase 1):

| Parameter | Description |
|---|---|
| `/wealth-management-portal/platform/account-id` | 12-digit AWS account ID |
| `/wealth-management-portal/platform/app-name` | App name for resource naming (≤6 chars, lowercase alphanumeric) |
| `/wealth-management-portal/platform/env-name` | Environment name (≤6 chars, lowercase alphanumeric) |
| `/wealth-management-portal/platform/primary-region` | Primary AWS region (e.g. `us-west-2`) |
| `/wealth-management-portal/platform/secondary-region` | Secondary AWS region (e.g. `us-east-1`) |
| `/wealth-management-portal/platform/admin-role` | IAM role name for Lake Formation admin (e.g. `Admin`) |

**Application parameters** (existing — already used by `ci-infra`):

All parameters under `/wealth-management-portal/*` as defined in `setup.mjs` SSM_PARAMS and `ci-stack.ts`.

### Setup Script

A new dual-mode script (`scripts/setup-ssm-params.sh`) that populates all SSM parameters for both phases.

**Interactive mode (default)** — prompts for each value with smart defaults:

```
$ ./scripts/setup-ssm-params.sh

🔧 Wealth Management Portal — Setup

AWS Account ID [123456789012]:          ← auto-detected via aws sts get-caller-identity
App name [advisor]:                     ← sensible default
Env name [dev1]:                        ← sensible default
Primary region [us-west-2]:             ← from AWS_DEFAULT_REGION or aws configure get region
Secondary region [us-east-1]:           ← auto-picks a different region than primary
Admin role name [Admin]:                ← default
Redshift workgroup [default-workgroup]: ← could query SSM if data-platform already deployed
Redshift database [dev]:                ← data-platform default
SES sender email []:                    ← optional
Tavily API key []:                      ← optional
Report Bedrock model [us.anthropic.claude-sonnet-4-5-20250929-v1:0]: ← default
Theme Bedrock model [us.anthropic.claude-haiku-4-5-20251001-v1:0]:   ← default
Deploy bastion [true]:                  ← default true for first-time setup

Create IAM role 'Admin'? [Y/n]:        ← auto-creates if it doesn't exist

Writing 15 parameters to SSM... ✓
```

**Non-interactive mode (`--ci`)** — reads all values from CLI arguments or environment variables, no prompts:

```bash
./scripts/setup-ssm-params.sh --ci \
  --app-name advisor \
  --env-name dev1 \
  --primary-region us-west-2 \
  --secondary-region us-east-1
```

**Behavior:**
1. Auto-detects account ID and current region when not provided
2. Shows defaults in brackets, accepts Enter to confirm (interactive mode)
3. Validates naming rules (same as `init.sh` — lowercase alphanumeric, ≤6 chars for app/env)
4. Creates the `Admin` IAM role if it doesn't exist (with user confirmation in interactive mode, automatic in `--ci` mode)
5. Writes all parameters to SSM via `PutParameter --overwrite` (idempotent)
6. Is safe to re-run — updates existing parameters, skips IAM resources that already exist

This replaces the interactive `make init` + `pnpm nx setup` flow.

---

## Phase 1: Platform Buildspec (`buildspec-platform.yml`)

### What It Automates

| Step | Make Target(s) | Automated? | Notes |
|---|---|---|---|
| Init (template resolution) | `make init` | ✅ | Non-interactive: inject values from SSM into env vars, run `init.sh` via heredoc |
| Terraform backend | `deploy-tf-backend-cf-stack` | ✅ | Fully automatable |
| Foundation (KMS, IAM, S3, VPC, MSK) | `deploy-foundation-all` | ✅ | Includes MSK Lambda layer build |
| IAM Identity Center | `deploy-idc-acc` | ✅ | Automatable |
| MFA disable | `disable-mfa` | ✅ | Optional, controlled by parameter |
| SageMaker Domain | `deploy-sagemaker-domain` | ✅ | Automatable |
| Glue JARs + Lake Formation | `deploy-glue-jars`, `deploy-lake-formation-all` | ✅ | Automatable |
| Athena | `deploy-athena` | ✅ | Automatable |
| Financial Advisor data lake | `deploy-financial-advisor-all` | ✅ | Starts Glue jobs |
| **Glue job wait gate** | (none — currently manual) | ✅ | New: poll `aws glue get-job-runs` until all 24 jobs succeed |
| SageMaker Projects | `deploy-sagemaker-projects` | ✅ | Includes `wait-datazone-stacks` — already polls CFN for `DataZone-Env-*` stacks after each project deploy. No new script needed. |
| Lake Formation S3 Tables grants | `grant-s3table-lakeformation-permissions` | ✅ | Must run after projects |
| Redshift LF readonly admin | `set-up-redshift-lf-readonly-admin` | ✅ | Must run after projects |
| Redshift DDL | `deploy-redshift-ddl` | ✅ | Automatable |
| QuickSight subscription | `deploy-quicksight-subscription` | ✅ | No dependency on QuickSight role — just creates the account subscription |
| RUM tables | `create-rum-all` | ✅ | No QuickSight dependency — just Redshift tables |
| QuickSight dataset | `deploy-quicksight-dataset` | ✅ | VPC connection takes `role_arn` directly — no console role assignment needed (Issue 27) |

### Manual Steps (cannot automate — documented as post-build instructions)

| Step | Why Manual | Post-Build Instruction |
|---|---|---|
| IDC password resets | No `sso-admin` or `identitystore` API for password reset/invite — confirmed by AWS re:Post and API reference exhaustive review | Print IDC user list + console URL |

> **QuickSight role assignment** — previously listed as manual, now confirmed automatable. The `aws_quicksight_vpc_connection` resource accepts `role_arn` directly; the console "Use an existing role" step only sets the account-level default role, which is not required for VPC connections. Smoke tested and confirmed (Issue 27).
> **Redshift GRANT** — automated in Issue 26b via `grant-redshift-admin-access` make target.

### Buildspec Structure

```yaml
# buildspec-platform.yml
version: 0.2

env:
  parameter-store:
    ACCOUNT_ID: /wealth-management-portal/platform/account-id
    APP_NAME: /wealth-management-portal/platform/app-name
    ENV_NAME: /wealth-management-portal/platform/env-name
    PRIMARY_REGION: /wealth-management-portal/platform/primary-region
    SECONDARY_REGION: /wealth-management-portal/platform/secondary-region
    ADMIN_ROLE: /wealth-management-portal/platform/admin-role

phases:
  install:
    runtime-versions:
      python: 3.12
    commands:
      - yum install -y jq make
      - pip install --upgrade pip

  pre_build:
    commands:
      # Non-interactive init — feed values via env vars, skip prompts
      - cd data-platform
      - scripts/ci-init.sh  # New script: resolves templates without prompts

  build:
    commands:
      - cd data-platform
      # Step 1: Terraform backend
      - make deploy-tf-backend-cf-stack
      # Step 2: Foundation
      - make deploy-foundation-all
      # Step 3: IAM Identity Center
      - make deploy-idc-acc
      # Step 4: SageMaker Domain
      - make deploy-sagemaker-domain
      # Step 5: Glue + Lake Formation
      - make deploy-glue-jars
      - make deploy-lake-formation-all
      # Step 6: Athena
      - make deploy-athena
      # Step 7: Financial Advisor data lake
      - make deploy-financial-advisor-all
      # Step 8: Wait for all 24 Glue jobs to complete
      - scripts/wait-glue-jobs.sh
      # Step 9: SageMaker Projects
      - make deploy-sagemaker-projects
      # Step 10: Post-project grants
      - make grant-s3table-lakeformation-permissions
      - make set-up-redshift-lf-readonly-admin
      # Step 11: Redshift DDL
      - make deploy-redshift-ddl
      # Step 12: QuickSight subscription + RUM (dataset deployed separately — see post_build)
      - make deploy-quicksight-subscription
      - make create-rum-all

  post_build:
    commands:
      # Print manual steps the developer must complete
      - echo "============================================"
      - echo "MANUAL STEPS REQUIRED — complete these in the AWS Console:"
      - echo "============================================"
      - echo ""
      - echo "1. RESET IDC PASSWORDS"
      - echo "   Open IAM Identity Center console and reset passwords for all created users."
      - echo ""
      - echo "2. GRANT REDSHIFT ACCESS"
      - echo "   Connect to the producer Redshift workgroup in Query Editor v2 as admin."
      - echo "   Run:"
      - echo "     CREATE USER \"IAMR:${ADMIN_ROLE}\" PASSWORD DISABLE;"
      - echo "     GRANT USAGE ON SCHEMA public TO \"IAMR:${ADMIN_ROLE}\";"
      - echo "     GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"IAMR:${ADMIN_ROLE}\";"
      - echo "     ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO \"IAMR:${ADMIN_ROLE}\";"
      - echo ""
      - echo "3. ASSIGN QUICKSIGHT ROLE"
      - echo "   Open QuickSight admin > Permissions > AWS resources"
      - echo "   Choose 'Use an existing role' > Select ${APP_NAME}-${ENV_NAME}-quicksight-service-role"
      - echo ""
      - echo "4. DEPLOY QUICKSIGHT DATASET (after step 3)"
      - echo "   aws codebuild start-build --project-name wealth-mgmt-platform-deploy \\"
      - echo "     --buildspec-override 'version: 0.2\nphases:\n  build:\n    commands:\n      - cd data-platform && make deploy-quicksight-dataset'"
```

### New Scripts Required

#### `data-platform/scripts/ci-init.sh`

Non-interactive replacement for `make init`. Reads `APP_NAME`, `ENV_NAME`, etc. from environment variables (injected by CodeBuild from SSM) and resolves all `.template` files without prompts.

#### `data-platform/scripts/wait-glue-jobs.sh`

Polls all 24 financial-advisor Glue jobs until they reach `SUCCEEDED` or `FAILED`. Fails the build if any job fails. Timeout: 60 minutes.

```bash
# Pseudocode
for each table in FINANCIAL_ADVISOR_TABLES:
  poll aws glue get-job-runs --job-name "financial-advisor-load-$table"
  until status == SUCCEEDED or FAILED
  fail build if any FAILED
```

### Timeout & Compute

- **Timeout**: 4 hours (Terraform deploys + Glue jobs + CloudFormation waits)
- **Compute**: `BUILD_GENERAL1_LARGE` (Terraform + MSK Lambda layer build benefit from more CPU/memory)
- **Image**: Amazon Linux 2 standard (Terraform, make, Python, jq pre-installed or easily added)

---

## Phase 2: Application Buildspec (`buildspec-app.yml`)

### What It Automates

| Step | Command | Automated? | Notes |
|---|---|---|---|
| Install dependencies | `pnpm install` | ✅ | |
| Generate `.env` from SSM | `scripts/generate-env-from-ssm.sh` | ✅ | New script — replaces interactive `pnpm nx setup` |
| Build infra | `pnpm nx run infra:build` | ✅ | |
| CDK bootstrap | `pnpm nx bootstrap @wealth-management-portal/infra` | ✅ | Idempotent |
| CDK deploy | `pnpm nx deploy @wealth-management-portal/infra` | ✅ | |
| Lake Formation grants | `pnpm nx grant-lf-permissions @wealth-management-portal/infra` | ✅ | Idempotent |
| Redshift grants | `pnpm nx grant-redshift-permissions @wealth-management-portal/infra` | ✅ | Idempotent |
| Create test user | `pnpm nx create-user @wealth-management-portal/infra` | ✅ | Add `--email`/`--password` flags to `create-user.mjs` for non-interactive mode |
| Load Neptune data | `uv run python scripts/load-neptune-data.py --region $AWS_REGION` | ✅ | Idempotent |

### Buildspec Structure

```yaml
# buildspec-app.yml
version: 0.2

env:
  parameter-store:
    AWS_REGION: /wealth-management-portal/aws-region
    REDSHIFT_VPC_ID: /wealth-management-portal/redshift-vpc-id
    PRIVATE_SUBNET_IDS: /wealth-management-portal/private-subnet-ids
    REDSHIFT_SECURITY_GROUP_ID: /wealth-management-portal/redshift-security-group-id
    PRIVATE_ROUTE_TABLE_ID: /wealth-management-portal/private-route-table-id
    REDSHIFT_WORKGROUP: /wealth-management-portal/redshift-workgroup
    REDSHIFT_DATABASE: /wealth-management-portal/redshift-database
    SES_SENDER_EMAIL: /wealth-management-portal/ses-sender-email
    REPORT_BEDROCK_MODEL_ID: /wealth-management-portal/report-bedrock-model-id
    TAVILY_API_KEY: /wealth-management-portal/tavily-api-key
    THEME_BEDROCK_MODEL_ID: /wealth-management-portal/theme-bedrock-model-id
    DEPLOY_BASTION: /wealth-management-portal/deploy-bastion
    PRIVATE_SUBNET_AZ: /wealth-management-portal/private-subnet-az
    TEST_USER_EMAIL: /wealth-management-portal/test-user-email
    TEST_USER_PASSWORD: /wealth-management-portal/test-user-password

phases:
  install:
    runtime-versions:
      python: 3.12
    commands:
      # Node 22 via n
      - curl -fsSL https://raw.githubusercontent.com/tj/n/master/bin/n | bash -s 22
      - export PATH="/usr/local/bin:$PATH"
      # pnpm
      - corepack enable
      - corepack prepare pnpm@latest --activate
      # uv
      - curl -LsSf https://astral.sh/uv/install.sh | sh
      - export PATH="$HOME/.local/bin:$PATH"
      # Dependencies
      - pnpm install --frozen-lockfile
      # Python deps: UV workspace (19 packages) + advisor_chat (separate workspace)
      - uv sync --frozen
      - cd packages/advisor_chat && uv sync --frozen && cd ../..

  pre_build:
    commands:
      - export PATH="/usr/local/bin:$HOME/.local/bin:$PATH"
      # Generate .env from environment variables (injected from SSM by CodeBuild)
      - scripts/generate-env-from-ssm.sh

  build:
    commands:
      - export PATH="/usr/local/bin:$HOME/.local/bin:$PATH"
      # Build + deploy
      - pnpm nx run infra:build
      - pnpm nx bootstrap @wealth-management-portal/infra
      - pnpm nx deploy @wealth-management-portal/infra
      # Post-deploy grants
      - pnpm nx grant-lf-permissions @wealth-management-portal/infra
      - pnpm nx grant-redshift-permissions @wealth-management-portal/infra
      # Load graph data
      - uv run python scripts/load-neptune-data.py --region $AWS_REGION
      # Create test user (non-interactive — email/password from SSM)
      - pnpm nx create-user @wealth-management-portal/infra -- --email=$TEST_USER_EMAIL --password=$TEST_USER_PASSWORD

  post_build:
    commands:
      - export PATH="/usr/local/bin:$HOME/.local/bin:$PATH"
      # Print the CloudFront URL
      - echo "============================================"
      - echo "DEPLOYMENT COMPLETE"
      - echo "============================================"
      - pnpm nx outputs @wealth-management-portal/infra 2>/dev/null | grep -i 'domain\|website\|cloudfront' || echo "Check CloudFormation outputs for the website URL"
      - echo ""
      - echo "Test user created with email: $TEST_USER_EMAIL"
```

### New Scripts Required

#### `scripts/generate-env-from-ssm.sh`

Generates `.env` from environment variables that CodeBuild already injected from SSM. No AWS API calls needed — just writes the env vars to a file.

```bash
# Writes .env from the environment variables CodeBuild injected
cat > .env <<EOF
AWS_REGION=${AWS_REGION}
AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}
USE_DEFAULT_AWS_CREDENTIALS=true
REDSHIFT_WORKGROUP=${REDSHIFT_WORKGROUP}
REDSHIFT_DATABASE=${REDSHIFT_DATABASE}
REDSHIFT_VPC_ID=${REDSHIFT_VPC_ID}
PRIVATE_SUBNET_IDS=${PRIVATE_SUBNET_IDS}
REDSHIFT_SECURITY_GROUP_ID=${REDSHIFT_SECURITY_GROUP_ID}
PRIVATE_ROUTE_TABLE_ID=${PRIVATE_ROUTE_TABLE_ID}
REPORT_BEDROCK_MODEL_ID=${REPORT_BEDROCK_MODEL_ID}
THEME_BEDROCK_MODEL_ID=${THEME_BEDROCK_MODEL_ID}
DEPLOY_BASTION=${DEPLOY_BASTION:-false}
PRIVATE_SUBNET_AZ=${PRIVATE_SUBNET_AZ:-}
SES_SENDER_EMAIL=${SES_SENDER_EMAIL:-}
TAVILY_API_KEY=${TAVILY_API_KEY:-}
STAGE_NAME=${STAGE_NAME:-sandbox}
EOF
```

### Timeout & Compute

- **Timeout**: 30 minutes (matches existing `ci-stack.ts`)
- **Compute**: `BUILD_GENERAL1_MEDIUM` (sufficient for CDK synth + deploy)
- **Image**: Amazon Linux 2 ARM (`aws/codebuild/amazonlinux2-aarch64-standard:3.0` — matches existing)

---

## Implementation Steps

Steps are organized as independent work units that can be delegated to parallel subagents. The dependency graph is:

```
Track A (no deps):  WU-1  WU-2  WU-3  WU-4  WU-5  WU-6
                      │     │     │     │
Track B (depends):    └─────┴─────┴─────┴──▶  WU-7 (buildspecs — needs WU-2,3,4,5)
                                               │
Track C (depends):                             └──▶  WU-8 (ci-stack — needs WU-7)
                                                      │
Track D (depends):                                    └──▶  WU-9 (docs — needs all)
```

WU-1 through WU-6 can run in parallel. WU-7 depends on WU-2/3/4/5 (references those scripts). WU-8 depends on WU-7. WU-9 depends on all.

---

### WU-1: SSM Setup Script

**Create:** `scripts/setup-ssm-params.sh`

**Context to read:** `scripts/setup.mjs` (existing interactive setup — understand what SSM params it creates), `.env.example` (all env vars and their defaults)

**What it does:** Dual-mode script (interactive default + `--ci` flag) that populates ALL SSM parameters for both Phase 1 (platform) and Phase 2 (application), and optionally creates the `Admin` IAM role.

**SSM parameters to write:**

Platform params (new):
| SSM Path | Default | Validation |
|---|---|---|
| `/wealth-management-portal/platform/account-id` | auto-detect via `aws sts get-caller-identity` | 12 digits |
| `/wealth-management-portal/platform/app-name` | `advisor` | lowercase alphanumeric, ≤6 chars |
| `/wealth-management-portal/platform/env-name` | `dev1` | lowercase alphanumeric, ≤6 chars |
| `/wealth-management-portal/platform/primary-region` | auto-detect via `aws configure get region` or `AWS_DEFAULT_REGION` | valid region |
| `/wealth-management-portal/platform/secondary-region` | auto-pick different region than primary (e.g. if primary=us-west-2, default=us-east-1) | valid region |
| `/wealth-management-portal/platform/admin-role` | `Admin` | non-empty |

Application params (match existing `ci-stack.ts` env vars):
| SSM Path | Default | Type |
|---|---|---|
| `/wealth-management-portal/aws-region` | same as primary-region | String |
| `/wealth-management-portal/redshift-vpc-id` | (no default — prompted) | String |
| `/wealth-management-portal/private-subnet-ids` | (no default — prompted) | String |
| `/wealth-management-portal/redshift-security-group-id` | (no default — prompted) | String |
| `/wealth-management-portal/private-route-table-id` | (no default — prompted) | String |
| `/wealth-management-portal/redshift-workgroup` | (no default — prompted) | String |
| `/wealth-management-portal/redshift-database` | `dev` | String |
| `/wealth-management-portal/ses-sender-email` | (empty — optional) | String |
| `/wealth-management-portal/report-bedrock-model-id` | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` | String |
| `/wealth-management-portal/tavily-api-key` | (empty — optional) | SecureString |
| `/wealth-management-portal/theme-bedrock-model-id` | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` | String |
| `/wealth-management-portal/deploy-bastion` | `true` | String |
| `/wealth-management-portal/private-subnet-az` | auto-detect from first subnet if available | String |
| `/wealth-management-portal/enable-compliance-reporting` | `false` | String |
| `/wealth-management-portal/compliance-reporting-bucket` | (empty) | String |
| `/wealth-management-portal/test-user-email` | (prompted) | String |
| `/wealth-management-portal/test-user-password` | (prompted) | SecureString |

**Interactive mode behavior:**
- Each param: `Param description [default]: ` — Enter accepts default
- App params that depend on data-platform (VPC, subnets, security group, route table, workgroup) should note: "These will be available after Phase 1 deploys. Leave blank now and re-run this script after Phase 1, or enter manually."
- After all params: `Create IAM role 'Admin'? [Y/n]:` — checks if role exists first via `aws iam get-role`, creates if missing
- Uses `aws ssm put-parameter --overwrite` for all writes (idempotent)

**Non-interactive mode (`--ci`):**
- All values from env vars or `--flag=value` CLI args
- Auto-creates Admin role without prompting
- Fails with clear error if required params missing

**Validation (reuse from `data-platform/init.sh`):**
```bash
validate_name() — lowercase alphanumeric, ≤6 chars (for app-name, env-name)
```

**Acceptance criteria:**
- `./scripts/setup-ssm-params.sh` runs interactively, shows defaults, writes all params
- `./scripts/setup-ssm-params.sh --ci --app-name=x --env-name=y` runs non-interactively
- Re-running is a no-op (idempotent)
- Admin role created if missing, skipped if exists
- Script is `chmod +x`, has `#!/usr/bin/env bash`, uses `set -euo pipefail`

---

### WU-2: Non-Interactive Platform Init

**Create:** `data-platform/scripts/ci-init.sh`

**Context to read:** `data-platform/init.sh` (the existing interactive init — copy `resolve_template` and `validate_name` functions verbatim, copy the template file list verbatim)

**What it does:** Non-interactive replacement for `make init`. Reads 6 values from environment variables (set by CodeBuild from SSM), derives 2 more, resolves all `.template` files.

**Required environment variables (input):**
- `AWS_ACCOUNT_ID` (or `ACCOUNT_ID` — support both, CodeBuild sets `ACCOUNT_ID`)
- `APP_NAME`
- `ENV_NAME`
- `AWS_PRIMARY_REGION` (or `PRIMARY_REGION` — support both)
- `AWS_SECONDARY_REGION` (or `SECONDARY_REGION` — support both)
- `ADMIN_ROLE`

**Derived variables:**
- `AWS_DEFAULT_REGION` = `AWS_PRIMARY_REGION`
- `TF_S3_BACKEND_NAME` = `${APP_NAME}-${ENV_NAME}-tf-back-end`

**Algorithm:**
1. Map CodeBuild env var names to init.sh names (e.g. `ACCOUNT_ID` → `AWS_ACCOUNT_ID`, `PRIMARY_REGION` → `AWS_PRIMARY_REGION`)
2. Validate `APP_NAME` and `ENV_NAME` (reuse `validate_name` from init.sh)
3. Fail with clear error if any required var is missing
4. Set `ENV_KEYS` array (same 8 keys as init.sh)
5. Copy `resolve_template` function from init.sh verbatim
6. Copy the `templateFilePaths` array from init.sh verbatim (the list of ~60 output paths)
7. Loop and resolve, same as init.sh

**Template resolution mechanism (from init.sh — copy exactly):**
```bash
resolve_template() {
    local templatePath="$1"
    local outputPath="${templatePath%.template}"
    local resolvedContent="$(cat "$templatePath")"
    local varName
    while read varName; do
        local envVarValue="${!varName}"
        if [[ "$envVarValue" == "blank" ]]; then envVarValue=""; fi
        resolvedContent="$(echo "$resolvedContent" | sed "s|###${varName}###|${envVarValue}|g;")"
    done <<< "$(IFS=$'\n'; echo -e "${ENV_KEYS[*]}")"
    echo "$resolvedContent" > "$outputPath"
}
```

**Acceptance criteria:**
- Given `APP_NAME=test ENV_NAME=dev1 AWS_ACCOUNT_ID=123456789012 AWS_PRIMARY_REGION=us-west-2 AWS_SECONDARY_REGION=us-east-1 ADMIN_ROLE=Admin`, running `ci-init.sh` produces the same output files as `init.sh` would with those interactive inputs
- Fails with non-zero exit and clear message if any required env var is missing
- Script is `chmod +x`, has `#!/usr/bin/env bash`, uses `set -euo pipefail`

---

### WU-3: Glue Job Wait Script

**Create:** `data-platform/scripts/wait-glue-jobs.sh`

**Context to read:** `data-platform/Makefile.template` — find the `FINANCIAL_ADVISOR_TABLES` variable for the list of 24 table names

**What it does:** Polls all 24 financial-advisor Glue jobs until every one reaches `SUCCEEDED` or `FAILED`. Fails the build if any job fails. Used by `buildspec-platform.yml` after `make deploy-financial-advisor-all`.

**The 24 tables:**
```
clients advisors accounts portfolios securities transactions holdings market_data performance fees goals interactions documents compliance research articles client_income_expense client_investment_restrictions client_reports crawl_log portfolio_config recommended_products theme_article_associations themes
```

**Algorithm:**
1. For each table, job name is `financial-advisor-load-${table}`
2. Get the most recent job run: `aws glue get-job-runs --job-name "..." --max-results 1 --region ${AWS_PRIMARY_REGION}`
3. Poll every 30 seconds until `JobRunState` is `SUCCEEDED`, `FAILED`, `STOPPED`, `ERROR`, or `TIMEOUT`
4. Track results: count succeeded, failed
5. After all jobs complete (or timeout), print summary
6. Exit 0 if all succeeded, exit 1 if any failed

**Environment variables (input):**
- `AWS_PRIMARY_REGION` — from the resolved Makefile or CodeBuild env

**Timeout:** 60 minutes total (configurable via `GLUE_WAIT_TIMEOUT` env var, default 3600 seconds)

**Acceptance criteria:**
- Polls all 24 jobs in parallel (check all, sleep, check all again — not sequential per-job)
- Prints progress: `[12/24] Waiting... clients: RUNNING, advisors: SUCCEEDED, ...`
- Exits 1 immediately if any job reaches FAILED/STOPPED/ERROR/TIMEOUT
- Exits 0 when all 24 reach SUCCEEDED
- Exits 1 if overall timeout exceeded
- Script is `chmod +x`, has `#!/usr/bin/env bash`, uses `set -euo pipefail`

---

### WU-4: Env File Generator

**Create:** `scripts/generate-env-from-ssm.sh`

**Context to read:** `.env.example` (to know all env vars the app expects)

**What it does:** Writes `.env` from environment variables that CodeBuild already injected from SSM. No AWS API calls needed (except account ID fallback). Used by `buildspec-app.yml` in `pre_build`.

**Output `.env` content:**
```bash
cat > .env <<EOF
AWS_REGION=${AWS_REGION}
AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}
USE_DEFAULT_AWS_CREDENTIALS=true
REDSHIFT_WORKGROUP=${REDSHIFT_WORKGROUP}
REDSHIFT_DATABASE=${REDSHIFT_DATABASE}
REDSHIFT_VPC_ID=${REDSHIFT_VPC_ID}
PRIVATE_SUBNET_IDS=${PRIVATE_SUBNET_IDS}
REDSHIFT_SECURITY_GROUP_ID=${REDSHIFT_SECURITY_GROUP_ID}
PRIVATE_ROUTE_TABLE_ID=${PRIVATE_ROUTE_TABLE_ID}
REPORT_BEDROCK_MODEL_ID=${REPORT_BEDROCK_MODEL_ID}
THEME_BEDROCK_MODEL_ID=${THEME_BEDROCK_MODEL_ID}
DEPLOY_BASTION=${DEPLOY_BASTION:-false}
PRIVATE_SUBNET_AZ=${PRIVATE_SUBNET_AZ:-}
SES_SENDER_EMAIL=${SES_SENDER_EMAIL:-}
TAVILY_API_KEY=${TAVILY_API_KEY:-}
STAGE_NAME=${STAGE_NAME:-sandbox}
ENABLE_COMPLIANCE_REPORTING=${ENABLE_COMPLIANCE_REPORTING:-false}
COMPLIANCE_REPORTING_BUCKET=${COMPLIANCE_REPORTING_BUCKET:-}
EOF
```

**Validation:** Check that `AWS_REGION`, `REDSHIFT_WORKGROUP`, `REDSHIFT_DATABASE`, `REDSHIFT_VPC_ID`, `PRIVATE_SUBNET_IDS`, `REDSHIFT_SECURITY_GROUP_ID`, `PRIVATE_ROUTE_TABLE_ID` are non-empty. Fail with clear error listing which vars are missing.

**Acceptance criteria:**
- Produces a valid `.env` file at the repo root
- Fails if required env vars are missing
- Script is `chmod +x`, has `#!/usr/bin/env bash`, uses `set -euo pipefail`

---

### WU-5: Idempotency Fixes

**Modify:** `data-platform/Makefile.template`, `data-platform/ddl-redshift/redshift-tables.sql`

**Context to read:** `data-platform/Makefile.template` (find the 3 targets below), `data-platform/ddl-redshift/redshift-tables.sql` (the 4 CREATE TABLE statements)

**Fix 1 — `create-glue-s3tables-catalog` target in `Makefile.template`:**

Current (fails on re-run):
```makefile
create-glue-s3tables-catalog:
	aws glue create-catalog \
        --cli-input-json '...' \
        --region "${AWS_PRIMARY_REGION}"
```

Change to:
```makefile
create-glue-s3tables-catalog:
	@aws glue get-catalog --name s3tablescatalog --region "${AWS_PRIMARY_REGION}" > /dev/null 2>&1 \
		&& echo "Glue catalog 's3tablescatalog' already exists — skipping" \
		|| aws glue create-catalog \
			--cli-input-json '...' \
			--region "${AWS_PRIMARY_REGION}"
```

**Fix 2 — `register-s3table-catalog-with-lake-formation` target in `Makefile.template`:**

Current (fails on re-run):
```makefile
register-s3table-catalog-with-lake-formation:
	aws lakeformation register-resource \
        --resource-arn "..." \
        --role-arn "..." \
        --with-federation \
        --region "${AWS_PRIMARY_REGION}"
```

Change to (append `|| true` — matches existing pattern in `grant-s3table-lakeformation-permissions`):
```makefile
register-s3table-catalog-with-lake-formation:
	aws lakeformation register-resource \
        --resource-arn "..." \
        --role-arn "..." \
        --with-federation \
        --region "${AWS_PRIMARY_REGION}" || true
```

**Fix 3 — `start-financial-advisor-glue-jobs` target in `Makefile.template`:**

Current (starts duplicate runs):
```makefile
start-financial-advisor-glue-jobs:
	@for table in $(FINANCIAL_ADVISOR_TABLES); do \
		aws glue start-job-run --region $(AWS_PRIMARY_REGION) --job-name "financial-advisor-load-$$table"; \
	done
```

Change to (skip if last run succeeded within 24h):
```makefile
start-financial-advisor-glue-jobs:
	@for table in $(FINANCIAL_ADVISOR_TABLES); do \
		LAST_STATE=$$(aws glue get-job-runs --job-name "financial-advisor-load-$$table" --max-results 1 --region $(AWS_PRIMARY_REGION) --query 'JobRuns[0].JobRunState' --output text 2>/dev/null || echo "NONE"); \
		if [ "$$LAST_STATE" = "SUCCEEDED" ]; then \
			echo "Skipping financial-advisor-load-$$table — last run SUCCEEDED"; \
		else \
			echo "Starting job: financial-advisor-load-$$table"; \
			aws glue start-job-run --region $(AWS_PRIMARY_REGION) --job-name "financial-advisor-load-$$table"; \
		fi; \
	done
```

**Fix 4 — `data-platform/ddl-redshift/redshift-tables.sql`:**

Change all 4 `CREATE TABLE` statements to `CREATE TABLE IF NOT EXISTS`:
- `CREATE TABLE public.articles` → `CREATE TABLE IF NOT EXISTS public.articles`
- `CREATE TABLE public.client_reports` → `CREATE TABLE IF NOT EXISTS public.client_reports`
- `CREATE TABLE public.theme_article_associations` → `CREATE TABLE IF NOT EXISTS public.theme_article_associations`
- `CREATE TABLE public.themes` → `CREATE TABLE IF NOT EXISTS public.themes`

**Acceptance criteria:**
- `make create-glue-s3tables-catalog` succeeds on both first run and re-run
- `make register-s3table-catalog-with-lake-formation` succeeds on both first run and re-run
- `make start-financial-advisor-glue-jobs` skips already-succeeded jobs
- `make deploy-redshift-ddl` succeeds on both first run and re-run
- No changes to any other targets

---

### WU-6: Non-Interactive `create-user.mjs`

**Modify:** `scripts/create-user.mjs`

**Context to read:** `scripts/create-user.mjs` (the full file — ~130 lines)

**What to change:** Add CLI argument parsing so the script works non-interactively when `--email` and `--password` are provided, while preserving the existing interactive behavior when they're not.

**Add at the top of `main()` function (before the interactive prompts):**
```javascript
const args = {};
for (const arg of process.argv.slice(2)) {
  const [key, ...rest] = arg.split('=');
  if (key.startsWith('--')) args[key.slice(2)] = rest.join('=');
}
```

**Then replace the 3 interactive prompt blocks:**

Email prompt — change from:
```javascript
let email;
while (true) {
  email = await ask('Email');
  if (isValidEmail(email)) break;
  console.log('  ⚠ Invalid email format. Try again.');
}
```
To:
```javascript
let email;
if (args.email) {
  if (!isValidEmail(args.email)) { console.error('  ✗ Invalid email format'); process.exit(1); }
  email = args.email;
} else {
  while (true) {
    email = await ask('Email');
    if (isValidEmail(email)) break;
    console.log('  ⚠ Invalid email format. Try again.');
  }
}
```

Username — change from:
```javascript
const defaultUsername = email.split('@')[0];
const username = await ask(`Username [${defaultUsername}]`) || defaultUsername;
```
To:
```javascript
const defaultUsername = email.split('@')[0];
const username = args.username || (args.email ? defaultUsername : (await ask(`Username [${defaultUsername}]`) || defaultUsername));
```

Password prompt — same pattern as email:
```javascript
let password;
if (args.password) {
  if (!isValidPassword(args.password)) { console.error('  ✗ Password must be at least 8 characters'); process.exit(1); }
  password = args.password;
} else {
  while (true) {
    password = await ask('Password (min 8 chars)');
    if (isValidPassword(password)) break;
    console.log('  ⚠ Password must be at least 8 characters. Try again.');
  }
}
```

**Also:** Close `rl` early if non-interactive (add after args parsing):
```javascript
if (args.email && args.password) rl.close();
```
And guard the existing `rl.close()` call after the interactive prompts to avoid double-close.

**Acceptance criteria:**
- `node scripts/create-user.mjs --email=test@example.com --password=MyPass123` works non-interactively
- `node scripts/create-user.mjs` still works interactively (prompts for email, username, password)
- Invalid `--email` or `--password` exits with non-zero and clear error
- Existing behavior unchanged when no args provided

---

### WU-7: Buildspecs

**Depends on:** WU-2 (ci-init.sh path), WU-3 (wait-glue-jobs.sh path), WU-4 (generate-env-from-ssm.sh path), WU-5 (idempotent targets)

**Create:** `buildspec-platform.yml`, `buildspec-app.yml` (both at repo root)

**Context to read:** `packages/ci-infra/buildspec.yml` (existing app buildspec — match install phase patterns), the buildspec YAML from the "Buildspec Structure" sections earlier in this plan document

**`buildspec-platform.yml`** — copy the YAML from the "Phase 1: Platform Buildspec" section of this plan verbatim. Ensure:
- `env.parameter-store` maps the 6 platform SSM params
- `install` installs Terraform (required — not pre-installed on CodeBuild AL2): `yum install -y yum-utils && yum-config-manager --add-repo https://rpm.releases.hashicorp.com/AmazonLinux/hashicorp.repo && yum install -y terraform-1.8.5`
- `pre_build` runs `data-platform/scripts/ci-init.sh`
- `build` runs the 12 make targets in order, with `data-platform/scripts/wait-glue-jobs.sh` after `deploy-financial-advisor-all`
- `post_build` prints the 4 manual steps with exact URLs, SQL, and commands

**`buildspec-app.yml`** — copy the YAML from the "Phase 2: Application Buildspec" section of this plan verbatim. Ensure:
- `env.parameter-store` maps all 17 application SSM params (including `TEST_USER_EMAIL`, `TEST_USER_PASSWORD`)
- `install` matches existing `packages/ci-infra/buildspec.yml` pattern (Node 22 via n, corepack pnpm, uv) but fixes Python deps: `uv sync --frozen` at root + `cd packages/advisor_chat && uv sync --frozen`
- `pre_build` runs `scripts/generate-env-from-ssm.sh`
- `build` runs: infra build, bootstrap, deploy, LF grants, Redshift grants, Neptune load, create-user with `--email`/`--password`
- `post_build` prints CloudFront URL and test user email

**Acceptance criteria:**
- Both files are valid YAML
- `buildspec-platform.yml` references `data-platform/scripts/ci-init.sh` and `data-platform/scripts/wait-glue-jobs.sh`
- `buildspec-app.yml` references `scripts/generate-env-from-ssm.sh`
- `buildspec-app.yml` uses `uv sync --frozen` (not `find ... -execdir`)

---

### WU-8: Update CI Stack

**Depends on:** WU-7 (needs to know buildspec names and SSM param paths)

**Modify:** `packages/ci-infra/src/stacks/ci-stack.ts`

**Context to read:** `packages/ci-infra/src/stacks/ci-stack.ts` (the full file — ~140 lines)

**Changes:**

1. **Add a second CodeBuild project** (`PlatformDeployProject`) for Phase 1:
   - `projectName`: `wealth-mgmt-platform-deploy`
   - `source`: same S3 bucket as existing project
   - `buildSpec`: same dummy inline buildspec (real one passed via `--buildspec-override`)
   - `environment.buildImage`: `LinuxBuildImage.STANDARD_7_0` (x86 — Terraform doesn't need ARM, and AL2 standard has more pre-installed tools)
   - `environment.computeType`: `LARGE`
   - `environment.privileged`: true
   - `timeout`: `Duration.hours(4)`
   - `environmentVariables`: the 6 platform SSM params:
     ```typescript
     ACCOUNT_ID: { value: '/wealth-management-portal/platform/account-id', type: PARAMETER_STORE },
     APP_NAME: { value: '/wealth-management-portal/platform/app-name', type: PARAMETER_STORE },
     ENV_NAME: { value: '/wealth-management-portal/platform/env-name', type: PARAMETER_STORE },
     PRIMARY_REGION: { value: '/wealth-management-portal/platform/primary-region', type: PARAMETER_STORE },
     SECONDARY_REGION: { value: '/wealth-management-portal/platform/secondary-region', type: PARAMETER_STORE },
     ADMIN_ROLE: { value: '/wealth-management-portal/platform/admin-role', type: PARAMETER_STORE },
     ```
   - Same `AdministratorAccess` policy, same S3 read grant, same cache config

2. **Add `TEST_USER_EMAIL` and `TEST_USER_PASSWORD` to existing project's env vars:**
   ```typescript
   TEST_USER_EMAIL: { value: '/wealth-management-portal/test-user-email', type: PARAMETER_STORE },
   TEST_USER_PASSWORD: { value: '/wealth-management-portal/test-user-password', type: PARAMETER_STORE },
   ```

3. **Update GitLab trigger role** to also grant `codebuild:StartBuild` and `codebuild:BatchGetBuilds` on the new platform project.

4. **Add CfnOutput** for the new project name: `PlatformCodeBuildProjectName`.

**Acceptance criteria:**
- `pnpm nx build @wealth-management-portal/ci-infra` compiles without errors
- Two CodeBuild projects defined: `wealth-mgmt-deploy` (existing, updated) and `wealth-mgmt-platform-deploy` (new)
- Platform project has 4-hour timeout, LARGE compute, x86 image
- App project has new `TEST_USER_EMAIL`/`TEST_USER_PASSWORD` env vars
- GitLab trigger role covers both projects

---

### WU-9: Documentation

**Depends on:** All other WUs

**Modify:** `README.md`, `packages/ci-infra/README.md`

**Context to read:** `README.md` (the "Getting Started" section), `packages/ci-infra/README.md` (if it exists)

**Add to `README.md`** — a new "## CI/CD Deployment" section after "Getting Started" that covers:

1. **Prerequisites**: AWS account, Bedrock model access enabled, git clone
2. **One-time setup**: `./scripts/setup-ssm-params.sh` (interactive — describe the prompts and defaults)
3. **Deploy CI infrastructure**: `pnpm install && pnpm nx deploy @wealth-management-portal/ci-infra`
4. **Deploy data platform**: `aws codebuild start-build --project-name wealth-mgmt-platform-deploy` + what to expect (~2 hours) + the 3 manual console steps + QuickSight dataset command
5. **Deploy application**: `aws codebuild start-build --project-name wealth-mgmt-deploy` + what to expect (~15 min) + CloudFront URL
6. **Re-deploying after code changes**: just re-trigger Phase 2
7. **Troubleshooting**: re-run is safe (idempotent), how to check build logs

**Acceptance criteria:**
- CI/CD section is self-contained — a new developer can follow it without reading the rest of the README
- Manual steps are clearly called out with exact console URLs and SQL
- No references to `datapipeline` IAM user

---

## Developer Experience Flow

### First-Time Setup (one-time per account)

```
1. Run: ./scripts/setup-ssm-params.sh
   (Interactive — prompts for app name, env name, regions, etc. with smart defaults)
   (Auto-creates IAM role 'Admin' for Lake Formation if it doesn't exist)
2. Deploy CI stack: cd packages/ci-infra && pnpm nx deploy
```

> **No IAM user needed.** The `datapipeline` IAM user from the manual workflow is not required — CodeBuild uses its own IAM service role (`AdministratorAccess`) instead.

### Deploy Data Platform

```
1. Upload source: ./scripts/upload-source.sh
2. Trigger CodeBuild project: wealth-mgmt-platform-deploy
   (or: aws codebuild start-build --project-name wealth-mgmt-platform-deploy \
        --buildspec-override buildspec-platform.yml)
3. Wait ~2 hours
4. Complete 1 manual console step (printed in build output):
   a. Reset IDC passwords
```

### Deploy Application

```
1. Upload source (if changed since last upload): ./scripts/upload-source.sh
2. Trigger CodeBuild project: wealth-mgmt-deploy
   (or: aws codebuild start-build --project-name wealth-mgmt-deploy \
        --buildspec-override buildspec-app.yml)
3. Wait ~15 minutes
4. Open CloudFront URL from build output — test user is already created
```

### Re-deploy After Code Changes

Only Phase 2 needs to re-run — triggered automatically by GitLab CI or manually.

---

## Risk & Mitigation

| Risk | Impact | Mitigation |
|---|---|---|
| Glue jobs fail silently | Phase 1 proceeds with missing data | `wait-glue-jobs.sh` polls and fails the build on any job failure |
| CloudFormation DataZone stacks timeout | Phase 1 hangs | Existing `wait-datazone-stacks` target handles this; CodeBuild 4-hour timeout as backstop |
| SSM parameters missing or wrong | Build fails early with cryptic errors | `ci-init.sh` and `generate-env-from-ssm.sh` validate required values upfront |
| Terraform state corruption on re-run | Broken data-platform | Terraform is idempotent by design; `init` + `apply` handles drift |
| Manual steps forgotten | Incomplete setup | `post_build` phase prints clear, numbered instructions |
| CodeBuild 8-hour limit | Single buildspec times out | Two-buildspec split keeps each well under limit |

---

## Rollback & Idempotency

### Idempotency

Both buildspecs are designed to be re-triggered after a failure without manual cleanup.

**Phase 2 (app) — fully idempotent.** `cdk deploy`, `grant-lf-permissions`, `grant-redshift-permissions`, and `load-neptune-data.py` are all no-ops when nothing has changed.

**Phase 1 (platform) — mostly idempotent.** Terraform `init` + `apply` handles drift automatically. A few targets need hardening guards for safe re-runs:

| Target | Issue on Re-run | Guard |
|---|---|---|
| `create-glue-s3tables-catalog` | Fails if catalog already exists | Add pre-check or `|| true` in Makefile target |
| `register-s3table-catalog-with-lake-formation` | Fails if already registered | Add pre-check or `|| true` in Makefile target |
| `start-financial-advisor-glue-jobs` | Starts new runs even if previous succeeded | Check last run status per job in Makefile; skip if `SUCCEEDED` within last 24h |
| `deploy-redshift-ddl` | DDL scripts must use `CREATE TABLE IF NOT EXISTS` / `CREATE OR REPLACE VIEW` | Fix DDL scripts directly (`redshift-tables.sql`) |

These guards belong in the Makefile/scripts (not the buildspec) because developers also run these targets manually. The codebase already follows this pattern — `grant-s3table-lakeformation-permissions` uses `|| true`, `redshift-rum-tables.sql` uses `IF NOT EXISTS`.

### Stuck Builds

If a build hangs (not failing, just stuck):

1. **Stop the build** — CodeBuild console or `aws codebuild stop-build --id <build-id>`
2. **No rollback needed** — Terraform targets are sequential and atomic per-module. A stopped build means the last target either completed fully or never started. CloudFormation stacks roll back on their own if interrupted mid-create.
3. **Re-trigger the buildspec** — idempotency means completed steps are skipped.

The 4-hour timeout (Phase 1) and 30-minute timeout (Phase 2) act as ultimate backstops.

### Failed Builds

1. Read the build logs to identify the failing target
2. Fix the root cause (bad parameter, permission, quota, etc.)
3. Re-trigger the same buildspec — no need to tear down first

### Full Teardown (if needed)

Not part of the CI buildspecs — these are manual, destructive operations:

- **Phase 2**: `pnpm nx destroy @wealth-management-portal/infra`
- **Phase 1**: `make destroy-all` (runs `destroy-*` targets in reverse order)

---

## Out of Scope

- **Fully eliminating manual steps** — IDC password resets require console access (no API available). All other previously-manual steps (Redshift grants, QuickSight role assignment, QuickSight dataset deploy) have been automated.
- **GitLab pipeline integration** — the existing `.gitlab-ci.yml` / trigger role setup is already handled by `ci-infra`. This plan focuses on the buildspecs themselves.
- **Teardown automation** — reverse-order destroy is a separate concern.
- **Multi-account / multi-environment orchestration** — each account runs its own pair of buildspecs with its own SSM parameters.

