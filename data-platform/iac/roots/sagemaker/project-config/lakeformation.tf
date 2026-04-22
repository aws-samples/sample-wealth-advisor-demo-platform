// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

# Note: Lake Formation permissions for S3 Tables federated catalogs are complex
# and may require manual configuration through the AWS Console or CLI.
# The standard Terraform aws_lakeformation_permissions resource has limitations
# with federated S3 Tables catalogs.

# For now, permissions should be granted manually using:
# aws lakeformation grant-permissions \
#   --principal DataLakePrincipalIdentifier=<PRODUCER_ROLE_ARN> \
#   --resource '{"Catalog": {"Id": "<ACCOUNT_ID>:s3tablescatalog/financial-advisor-s3table"}}' \
#   --permissions "DESCRIBE" "CREATE_DATABASE" \
#   --region ###AWS_PRIMARY_REGION###

# Note: Lake Formation permissions for S3 Tables federated catalogs must be
# granted manually via AWS Console or CLI. Terraform doesn't support federated
# catalog permissions.

output "manual_lf_permissions_required" {
  sensitive = true
  value = <<-EOT
    Lake Formation permissions for S3 Tables must be granted manually.
    
    Use AWS Console: Lake Formation > Data lake permissions > Grant
    
    Producer Role: ${local.PRODUCER_ROLE}
    Consumer Role: ${local.CONSUMER_ROLE}
    Catalog: s3tablescatalog
    Database: financial_advisor
    
    Producer permissions: DESCRIBE, CREATE_TABLE, ALTER, DROP, SELECT, INSERT, DELETE
    Consumer permissions: DESCRIBE, SELECT
  EOT
}

