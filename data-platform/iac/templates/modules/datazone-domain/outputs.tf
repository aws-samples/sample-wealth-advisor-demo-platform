// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

output "domain_id" {

  description = "The ID of the Domain"
  value       = awscc_datazone_domain.domain.id
}

output "domain_arn" {

  description = "The Arn of the Domain"
  value       = awscc_datazone_domain.domain.arn
}

output "domain_url" {

  description = "The URL of the Domain Portal"
  value       = awscc_datazone_domain.domain.portal_url
}
