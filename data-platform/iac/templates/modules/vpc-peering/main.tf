// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

terraform {
  required_providers {
    aws = {
      source                = "hashicorp/aws"
      configuration_aliases = [aws.primary, aws.secondary]
    }
  }
}

resource "aws_vpc_peering_connection" "peering_connection" {

  provider = aws.primary

  peer_region = var.AWS_SECONDARY_REGION
  vpc_id      = var.PRIMARY_VPC_ID
  peer_vpc_id = var.SECONDARY_VPC_ID
  auto_accept = false

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = var.USAGE
    Name = "${var.APP}-${var.AWS_PRIMARY_REGION}-to-${var.AWS_SECONDARY_REGION}"
  }
}

resource "aws_vpc_peering_connection_accepter" "connection_acceptor" {

  provider = aws.secondary

  vpc_peering_connection_id = aws_vpc_peering_connection.peering_connection.id
  auto_accept               = true

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = var.USAGE
    Name = "${var.APP}-${var.AWS_PRIMARY_REGION}-to-${var.AWS_SECONDARY_REGION}"
  }
}

resource "aws_vpc_peering_connection_options" "requester_options" {

  provider = aws.primary

  vpc_peering_connection_id = aws_vpc_peering_connection_accepter.connection_acceptor.id

  requester {
    allow_remote_vpc_dns_resolution = true
  }
}

resource "aws_vpc_peering_connection_options" "acceptor_options" {

  provider = aws.secondary

  vpc_peering_connection_id = aws_vpc_peering_connection_accepter.connection_acceptor.id

  accepter {
    allow_remote_vpc_dns_resolution = true
  }
}

resource "aws_route" "primary_public_subnet_route" {

  provider = aws.primary

  route_table_id            = var.PRIMARY_PUBLIC_SUBNET_1_ROUTE_TABLE_ID
  destination_cidr_block    = var.SECONDARY_CIDR
  vpc_peering_connection_id = aws_vpc_peering_connection.peering_connection.id
}

resource "aws_route" "primary_private_subnet_1_route" {

  provider = aws.primary

  route_table_id            = var.PRIMARY_PRIVATE_SUBNET_1_ROUTE_TABLE_ID
  destination_cidr_block    = var.SECONDARY_CIDR
  vpc_peering_connection_id = aws_vpc_peering_connection.peering_connection.id
}

resource "aws_route" "primary_private_subnet_2_route" {

  provider = aws.primary

  route_table_id            = var.PRIMARY_PRIVATE_SUBNET_2_ROUTE_TABLE_ID
  destination_cidr_block    = var.SECONDARY_CIDR
  vpc_peering_connection_id = aws_vpc_peering_connection.peering_connection.id
}

resource "aws_route" "primary_private_subnet_3_route" {

  provider = aws.primary

  route_table_id            = var.PRIMARY_PRIVATE_SUBNET_3_ROUTE_TABLE_ID
  destination_cidr_block    = var.SECONDARY_CIDR
  vpc_peering_connection_id = aws_vpc_peering_connection.peering_connection.id
}

resource "aws_route" "secondary_public_subnet_route" {

  provider = aws.secondary

  route_table_id            = var.SECONDARY_PUBLIC_SUBNET_1_ROUTE_TABLE_ID
  destination_cidr_block    = var.PRIMARY_CIDR
  vpc_peering_connection_id = aws_vpc_peering_connection.peering_connection.id
}

resource "aws_route" "secondary_private_subnet_1_route" {

  provider = aws.secondary

  route_table_id            = var.SECONDARY_PRIVATE_SUBNET_1_ROUTE_TABLE_ID
  destination_cidr_block    = var.PRIMARY_CIDR
  vpc_peering_connection_id = aws_vpc_peering_connection.peering_connection.id
}

resource "aws_route" "secondary_private_subnet_2_route" {

  provider = aws.secondary

  route_table_id            = var.SECONDARY_PRIVATE_SUBNET_2_ROUTE_TABLE_ID
  destination_cidr_block    = var.PRIMARY_CIDR
  vpc_peering_connection_id = aws_vpc_peering_connection.peering_connection.id
}

resource "aws_route" "secondary_private_subnet_3_route" {

  provider                  = aws.secondary
  route_table_id            = var.SECONDARY_PRIVATE_SUBNET_3_ROUTE_TABLE_ID
  destination_cidr_block    = var.PRIMARY_CIDR
  vpc_peering_connection_id = aws_vpc_peering_connection.peering_connection.id
}
