// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

variable "AWS_ACCOUNT_ID" {

  type = string
}

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

variable "SSM_KMS_KEY_ALIAS" {

  type = string
}

variable "EBS_KMS_KEY_ALIAS" {

  type = string
}

variable "SECRETS_MANAGER_KMS_KEY_ALIAS" {

  type = string
}

variable "CURRENT_ROLE" {
  description = "The role used for deployment of the solution"
  type        = string
}