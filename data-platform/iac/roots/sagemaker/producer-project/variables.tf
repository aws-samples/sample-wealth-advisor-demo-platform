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

variable "S3_PRIMARY_KMS_KEY_ALIAS" {

  type = string
}

variable "S3_SECONDARY_KMS_KEY_ALIAS" {

  type = string
}

variable "S3BUCKET" {

  type = string
}

variable "SSM_KMS_KEY_ALIAS" {

  type = string
}

variable "PRODUCER_PROJECT_NAME" {

  type = string
}

variable "PRODUCER_PROJECT_DESCRIPTION" {

  type = string
}


variable "GLUE_DB_NAME" {

  type = string
}
