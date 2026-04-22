// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

variable "APP" {

  type = string
}

variable "ENV" {

  type = string
}

variable "capabilities" {

  type        = list(string)
  description = "A list of capabilities. Valid values: CAPABILITY_IAM, CAPABILITY_NAMED_IAM, CAPABILITY_AUTO_EXPAND"
  default     = ["CAPABILITY_IAM"]
}


variable "S3BUCKET" {

  type = string
}

variable "PROJECT_NAME" {

  type = string
}

variable "PROJECT_DESCRIPTION" {

  type = string
}


variable "USER_TYPE" {

  type = string
  default     = "user"
}

variable "GLUE_DB" {

  type = string
}

variable "SSM_KMS_KEY_ALIAS" {
  type = string
}

