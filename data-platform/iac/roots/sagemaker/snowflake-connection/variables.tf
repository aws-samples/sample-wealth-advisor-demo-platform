// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

variable "APP" {

  type        = string
  description = "Application name."
}

variable "ENV" {

  type        = string
  description = "Environment name."
}

variable "AWS_PRIMARY_REGION" {

  type        = string
  description = "The primary AWS region for deployment."
}

variable "AWS_SECONDARY_REGION" {

  description = "AWS Secondary Region"
  type        = string
}

variable "AWS_ACCOUNT_ID" {

  type        = string
  description = "AWS Account ID."
}

variable "SNOWFLAKE_USERNAME" {

  description = "Snowflake username for the DataZone connection."
  type        = string
  sensitive   = true
}

variable "SNOWFLAKE_PASSWORD" {

  description = "Snowflake password for the DataZone connection."
  type        = string
  sensitive   = true
}

variable "SNOWFLAKE_HOST" {

  description = "Snowflake account host URL (e.g., youraccount.snowflakecomputing.com)."
  type        = string
}

variable "SNOWFLAKE_PORT" {

  type        = string
  default     = "443"
  description = "Snowflake port number."
}

variable "SNOWFLAKE_DATABASE" {

  type        = string
  description = "Snowflake database name to connect to."
}

variable "SNOWFLAKE_WAREHOUSE" {

  type        = string
  description = "Snowflake warehouse to use."
}

variable "SNOWFLAKE_SCHEMA" {

  type        = string
  description = "Snowflake schema to use."
}

variable "SNOWFLAKE_CONNECTION_NAME" {

  type        = string
  description = "Name of the connection. Use 'snowflake' if in doubdt."
}

variable "SECRETS_MANAGER_KMS_KEY_ALIAS" {

  type = string
}

variable "SSM_KMS_KEY_ALIAS" {

  type = string
}
