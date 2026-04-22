// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

data "aws_caller_identity" "current" {}

locals {
  account_id    = data.aws_caller_identity.current.account_id
  bucket_name   = "${local.account_id}-${var.APP}-${var.ENV}-${var.NAME}"
}

resource "aws_s3_bucket" "bucket" {

  bucket = local.bucket_name

  force_destroy = true

  lifecycle {
    prevent_destroy = false
  }

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = var.USAGE
  }

  #checkov:skip=CKV_AWS_18: "Ensure the S3 bucket has access logging enabled": "Shared bucket module. Access logging requires a dedicated logging bucket to be passed in. TODO: Add optional logging_bucket variable to enable access logging."
  #checkov:skip=CKV2_AWS_61: "Ensure that an S3 bucket has a lifecycle configuration": "Skipping this for simplicity."
  #checkov:skip=CKV2_AWS_62: "Ensure S3 buckets should have event notifications enabled": "Skipping this as it will increase the cost of deploying the solution."
}

resource "aws_s3_bucket_ownership_controls" "bucket_ownership_controls" {

  bucket = aws_s3_bucket.bucket.id

  rule {
    object_ownership = "BucketOwnerPreferred"
  }

  #checkov:skip=CKV2_AWS_65: "Ensure access control lists for S3 buckets are disabled": "Recommended BucketOwnerEnforced does not work, only BucketOwnerPreferred works."
}

resource "aws_s3_bucket_acl" "bucket_acl" {

  bucket = aws_s3_bucket.bucket.id

  acl    = "private"

  depends_on = [aws_s3_bucket_ownership_controls.bucket_ownership_controls]
}

resource "aws_s3_bucket_public_access_block" "bucket_public_access_block" {

  bucket = aws_s3_bucket.bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "bucket_versioning" {

  bucket = aws_s3_bucket.bucket.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "bucket_encryption" {

  bucket = aws_s3_bucket.bucket.bucket

  rule {
    bucket_key_enabled = false
    apply_server_side_encryption_by_default {
      kms_master_key_id = var.CMK_ARN
      sse_algorithm     = "aws:kms"
    }
  }

  #checkov:skip=CKV2_AWS_67: "Ensure AWS S3 bucket encrypted with Customer Managed Key (CMK) has regular rotation": "All KMS Keys are configured with regular rotation."
}


