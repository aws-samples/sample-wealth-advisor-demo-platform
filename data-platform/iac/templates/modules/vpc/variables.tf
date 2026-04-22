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

variable "PRIVATE_SUBNETS" {

  type = list(string)
}

variable "PUBLIC_SUBNETS" {

  type = list(string)
}

variable "KMS_KEY" {

  type = string
}
