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

variable "LAMBDA_BUCKET" {
  description = "S3 bucket name for Lambda zip"
}

variable "LAMBDA_KEY" {
  description = "S3 key (path) to the zip file"
  default     = "lambda/instance_creation"
}
