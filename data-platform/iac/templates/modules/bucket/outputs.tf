// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

output "bucket_name" {

  description = "The name of the bucket"
  value       = aws_s3_bucket.bucket.bucket
}

output "bucket_arn" {

  description = "The ARN of the bucket"
  value       = aws_s3_bucket.bucket.arn
}

output "bucket_id" {

  description = "The ID of the bucket"
  value       = aws_s3_bucket.bucket.id
}

output "bucket_regional_domain_name" {

  description = "The bucket regional domain name"
  value       = aws_s3_bucket.bucket.bucket_regional_domain_name
}


