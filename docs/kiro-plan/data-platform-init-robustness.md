# Data Platform Init Robustness Fixes

## Background

A colleague attempted to set up the data-platform from scratch following the root README instructions and hit multiple blocking issues that cost 4+ hours and required recreating a burner AWS account.

### Issue 1: No input validation in `init.sh`

`init.sh` accepts `APP_NAME` and `ENV_NAME` with zero validation. These values are interpolated into S3 bucket names via the bucket Terraform module:

```
bucket_name = "${account_id}-${APP}-${ENV}-${NAME}"
```

S3 bucket naming rules require all lowercase, no underscores. But `init.sh` doesn't enforce this. If someone enters `My_App`, the bad value is silently written into 50+ template files, and errors only surface later during `terraform apply` — at which point recovery requires `git checkout` on all affected files.

The root README warns about hyphens but says nothing about uppercase or underscores.

### Issue 2: Buckets provider uses alias but modules use default provider

In `iac/roots/foundation/buckets/provider.tf`:

```hcl
provider "aws" {
  alias  = "primary"
  region = var.REGION
}
```

The provider is aliased as `"primary"`, but none of the bucket module calls pass `providers = { aws = aws.primary }`. Terraform falls back to the default AWS provider, which uses `AWS_DEFAULT_REGION` from the environment or `~/.aws/config`. If the user's CLI default region differs from the primary region set in `make init`, buckets are created in the wrong region.

Other foundation modules (VPC, KMS) don't have this bug — VPC defines a default (unaliased) provider set to `var.AWS_PRIMARY_REGION`.

### Issue 3: `init.sh` is a one-shot, non-idempotent operation

`init.sh` does a destructive find-and-replace of `###PLACEHOLDER###` tokens directly in working files. Once run, the placeholders are gone. Re-running `init.sh` does nothing because there are no more `###` patterns to replace. The only recovery is `git checkout` on all 50+ affected files.

## Fixes

### Fix 1: Add input validation to `init.sh`

Validate `APP_NAME` and `ENV_NAME` immediately after user input:
- Must be lowercase only (`[a-z0-9]`)
- No underscores, hyphens, or uppercase
- Must be 1-12 characters (to avoid AWS resource name length limits)
- Reject and re-prompt on invalid input

### Fix 2: Add default (unaliased) provider to buckets `provider.tf`

Add a default provider block set to `var.REGION` so that bucket modules (which don't specify a provider) use the correct region from `terraform.tfvars` instead of falling back to the CLI default.

### Fix 3: Make `init.sh` idempotent using `.template` files

- Rename each target file that contains `###` placeholders to a `.template` suffix (e.g. `terraform.tfvars.template`)
- `init.sh` reads from `.template` files and writes resolved output to the working file
- Templates stay intact in git with their `###` placeholders
- Generated files are gitignored
- Re-running `make init` regenerates everything from templates — safe to run any number of times

Special cases:
- `Makefile` is both a template target and the file that runs `make init` — it needs the `.template` treatment too, but the resolved Makefile must not be gitignored (it's needed by `make`)
- `set-env-vars.sh` replaces itself in-place — same treatment

## Files Changed

| File | Change |
|------|--------|
| `data-platform/init.sh` | Add validation + template-based generation |
| `data-platform/iac/roots/foundation/buckets/provider.tf` | Add default provider |
| `data-platform/set-env-vars.sh` → `set-env-vars.sh.template` | Rename to template |
| `data-platform/Makefile` → `Makefile.template` | Rename to template |
| 50+ `.tfvars` / `backend.tf` / `.json` files | Rename to `.template` suffix |
| `data-platform/.gitignore` | Ignore generated files |
| Root `README.md` | Update `APP_NAME` warning to include uppercase and underscores |
