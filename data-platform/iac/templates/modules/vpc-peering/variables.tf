// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

variable "APP" {

  type = string
}

variable "ENV" {

  type = string
}

variable "USAGE" {

  type = string
}

variable "AWS_PRIMARY_REGION" {

  type = string
}

variable "AWS_SECONDARY_REGION" {

  type = string
}

variable "PRIMARY_CIDR" {

  type = string
}

variable "SECONDARY_CIDR" {

  type = string
}

variable "PRIMARY_VPC_ID" {

  type = string
}

variable "SECONDARY_VPC_ID" {

  type = string
}

variable "PRIMARY_PUBLIC_SUBNET_1_ROUTE_TABLE_ID" {

  type = string
}

variable "PRIMARY_PRIVATE_SUBNET_1_ROUTE_TABLE_ID" {

  type = string
}

variable "PRIMARY_PRIVATE_SUBNET_2_ROUTE_TABLE_ID" {

  type = string
}

variable "PRIMARY_PRIVATE_SUBNET_3_ROUTE_TABLE_ID" {

  type = string
}

variable "SECONDARY_PUBLIC_SUBNET_1_ROUTE_TABLE_ID" {

  type = string
}

variable "SECONDARY_PRIVATE_SUBNET_1_ROUTE_TABLE_ID" {

  type = string
}

variable "SECONDARY_PRIVATE_SUBNET_2_ROUTE_TABLE_ID" {

  type = string
}

variable "SECONDARY_PRIVATE_SUBNET_3_ROUTE_TABLE_ID" {

  type = string
}
