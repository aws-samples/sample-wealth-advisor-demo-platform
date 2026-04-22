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

variable "AWS_REGION" {

  type = string
}

variable "CIDR" {

  type = string
}

variable "VPC_ID" {

  type = string
}

variable "PUBLIC_SUBNET_1" {

  type = string
}

variable "PUBLIC_SUBNET_2" {

  type = string
}

variable "PUBLIC_SUBNET_3" {

  type = string
}

variable "SUBNET_IDS" {

  type = list(string)
}
