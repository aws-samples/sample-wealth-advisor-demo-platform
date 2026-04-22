// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

output "dynamodb_endpoint_id" {

  description = "The DynamoDB Endpoint ID"
  value       = aws_vpc_endpoint.dynamodb_endpoint.id
}

output "secrets_manager_endpoint_id" {

  description = "The Secrets Manager Endpoint ID"
  value       = aws_vpc_endpoint.secrets_manager_endpoint.id
}

output "ssm_endpoint_id" {

  description = "The SSM Endpoint ID"
  value       = aws_vpc_endpoint.ssm_endpoint.id
}

output "execute_api_endpoint_id" {

  description = "The Execute API Endpoint ID"
  value       = aws_vpc_endpoint.execute_api_endpoint.id
}
