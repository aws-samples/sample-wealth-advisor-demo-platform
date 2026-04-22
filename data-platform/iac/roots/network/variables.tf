// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

variable "APP" {

  type = string
}

variable "ENV" {

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

variable "PRIMARY_PRIVATE_SUBNETS" {

  type = list(string)
}

variable "PRIMARY_PUBLIC_SUBNETS" {

  type = list(string)
}

variable "SECONDARY_CIDR" {

  type = string
}

variable "SECONDARY_PRIVATE_SUBNETS" {

  type = list(string)
}

variable "SECONDARY_PUBLIC_SUBNETS" {

  type = list(string)

}

variable "SSM_KMS_KEY_ALIAS" {

  type = string
}
