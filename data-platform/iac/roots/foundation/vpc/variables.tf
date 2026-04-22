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

variable "S3_KMS_KEY_ALIAS" {

  type = string
}

variable "SSM_KMS_KEY_ALIAS" {

  type = string
}

variable "DOMAIN_KMS_KEY_ALIAS" {
  
  type = string
}
