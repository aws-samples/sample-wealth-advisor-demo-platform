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

variable "CLOUDWATCH_KMS_KEY_ALIAS" {

  type = string
}

variable "smus_domain_execution_role_name" {

  description = "Name of the SMUS domain execution role"
  type        = string
}

variable "smus_domain_service_role_name" {

  description = "Name of the SMUS service role"
  type        = string
}

variable "smus_domain_provisioning_role_name" {

  description = "Name of the SMUS provisioning role"
  type        = string
}

variable "smus_domain_bedrock_model_manage_role_name" {

  description = "Name of the SMUS Bedrock Model Management Role"
  type        = string
}

variable "smus_domain_bedrock_model_consume_role_name" {

  description = "Name of the SMUS Bedrock Model Consumption Role"
  type        = string
}

variable "DOMAIN_KMS_KEY_ALIAS" {
  
  type = string
}
