// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

output "name" {

  description = "The Name of the VPC"
  value       = module.vpc.name
}

output "vpc_id" {

  description = "The ID of the VPC"
  value       = module.vpc.vpc_id
}

output "private_subnets" {

  description = "List of IDs of Private Subnets"
  value       = module.vpc.private_subnets
}

output "private_subnets_cidr_blocks" {

  description = "List of Private Subnets Cyber Blocks"
  value       = module.vpc.private_subnets_cidr_blocks
}

output "public_subnets" {

  description = "List of IDs of Public Subnets"
  value       = module.vpc.public_subnets
}

output "public_subnets_cidr_blocks" {

  description = "List of Public Subnets Cyber Blocks"
  value       = module.vpc.public_subnets_cidr_blocks
}

output "public_subnet_1_route_table_id" {

  description = "Public Subnet 1 Route Table ID"
  value       = data.aws_route_table.public_subnet_1_route_table.id
}

output "private_subnet_1_route_table_id" {

  description = "Private Subnet 1 Route Table ID"
  value       = data.aws_route_table.private_subnet_1_route_table.id
}

output "private_subnet_2_route_table_id" {

  description = "Private Subnet 2 Route Table ID"
  value       = data.aws_route_table.private_subnet_2_route_table.id
}

output "private_subnet_3_route_table_id" {

  description = "Private Subnet 3 Route Table ID"
  value       = data.aws_route_table.private_subnet_3_route_table.id
}
