// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

resource "random_string" "random_alphanumeric" {

  # No keepers block — the random suffix must remain stable across re-applies
  # to avoid destroying and recreating the SageMaker projects bucket.
  length  = 10
  special = false
  upper   = false
  lower   = true
  numeric = true
}

locals {
  smus_projects_bucket_name = "amazon-sagemaker-${local.account_id}-${local.region}-${random_string.random_alphanumeric.result}"
}

resource "aws_s3_bucket" "projects_bucket" {

  bucket = local.smus_projects_bucket_name

  #checkov:skip=CKV_AWS_18: "Ensure the S3 bucket has access logging enabled": "As this is project bucket, keeping it simple for now, will enable CRR in future if needed."
  #checkov:skip=CKV_AWS_144: "Ensure that S3 bucket has cross-region replication enabled": "As this is project bucket, keeping it simple for now, will enable CRR in future if needed."
  #checkov:skip=CKV_AWS_21: "Ensure all data stored in the S3 bucket have versioning enabled": "As this is project bucket, keeping it simple for now, will enable object versioning in future if needed."
  #checkov:skip=CKV2_AWS_61: "Ensure that an S3 bucket has a lifecycle configuration": "Skipping this for simplicity."
  #checkov:skip=CKV2_AWS_62: "Ensure S3 buckets should have event notifications enabled": "Skipping this as it will increase the cost of deploying the solution."
  #checkov:skip=CKV_AWS_53: "Ensure S3 bucket has block public ACLS enabled": "As this is project bucket, keeping it simple for now, will enable block public ACLS in future if needed."
  #checkov:skip=CKV_AWS_54: "Ensure S3 bucket has block public policy enabled": "As this is project bucket, keeping it simple for now, will enable block public policy in future if needed.
  #checkov:skip=CKV_AWS_55: "Ensure S3 bucket has ignore public ACLs enabled": "As this is project bucket, keeping it simple for now, will enable ignore public ACLs in future if needed."
  #checkov:skip=CKV_AWS_56: "Ensure S3 bucket has 'restrict_public_buckets' enabled": "As this is project bucket, keeping it simple for now, will enable restrict public bucket policies in future if needed."
  #checkov:skip=CKV2_AWS_6: "Ensure that S3 bucket has a Public Access block": "As this is project bucket, keeping it simple for now, will enable public access block in future if needed."
}

# TODO: Uncomment the below block, once the exact bucket policies required to allow project creation with stricter bucket policies are identified
# The following will fix CKV_AWS_53, CKV_AWS_54, CKV_AWS_55, CKV_AWS_56 and CKV2_AWS_6
# resource "aws_s3_bucket_public_access_block" "projects_bucket" {

#   bucket = aws_s3_bucket.projects_bucket.id
#   block_public_acls   = true
#   block_public_policy = true
#   restrict_public_buckets = true
#   ignore_public_acls = true
# }

resource "aws_s3_bucket_server_side_encryption_configuration" "projects_bucket" {

  bucket = aws_s3_bucket.projects_bucket.bucket

  rule {
    bucket_key_enabled = false
    # apply_server_side_encryption_by_default {
    #   kms_master_key_id = data.aws_kms_key.s3_kms_key.key_id
    #   sse_algorithm     = "aws:kms"
    # }
  }

  #checkov:skip=CKV2_AWS_67: "Ensure AWS S3 bucket encrypted with Customer Managed Key (CMK) has regular rotation": "All KMS Keys are configured with regular rotation."
}

resource "aws_s3_bucket_cors_configuration" "smus_projects_pbucket_cors" {

  bucket = aws_s3_bucket.projects_bucket.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["PUT", "POST", "GET", "DELETE"]
    allowed_origins = ["*"]
    expose_headers  = ["x-amz-version-id"]
  }
  depends_on = [aws_s3_bucket.projects_bucket]
}


# Save the AZ names in SSM Parameter Store
resource "aws_ssm_parameter" "smus_projects_bucket_s3_url" {

  name   = "/${var.APP}/${var.ENV}/smus_projects_bucket_s3_url"
  type   = "SecureString"
  value  = "s3://${local.smus_projects_bucket_name}"
  key_id = data.aws_kms_key.ssm_kms_key.key_id

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage       = "SMUS Domain Pre-req"
  }
  overwrite = true
}

