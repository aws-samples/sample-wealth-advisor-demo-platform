// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

output "vpc_id" {

  description = "The ID of the VPC"
  value       = aws_vpc.main.id
}

output "vpc_cidr_block" {

  description = "The CIDR block of the VPC"
  value       = aws_vpc.main.cidr_block
}

output "public_subnet_id" {

  description = "The ID of the public subnet"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {

  description = "The IDs of the private subnets"
  value       = aws_subnet.private[*].id
}

output "private_subnet_cidrs" {

  description = "The CIDR blocks of the private subnets"
  value       = aws_subnet.private[*].cidr_block
}

output "public_subnet_cidrs" {

  description = "The CIDR blocks of the private subnets"
  value       = aws_subnet.public[*].cidr_block
}

output "nat_gateway_id" {

  description = "The ID of the NAT Gateway"
  value       = aws_nat_gateway.main.id
}

output "nat_gateway_eip" {

  description = "The Elastic IP address of the NAT Gateway"
  value       = aws_eip.nat.public_ip
}

output "internet_gateway_id" {
  
  description = "The ID of the Internet Gateway"
  value       = aws_internet_gateway.main.id
}
