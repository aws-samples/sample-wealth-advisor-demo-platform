// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

variable "APP" {

  type = string
}

variable "ENV" {

  type = string
}


variable "KMS_KEY" {

  type = string
}

variable "USAGE" {

  type = string
}

variable "domain_id" {

  type = string
}

variable "datasource_name" {
  type = string
}

variable "datasource_type" {
  type = string
}

variable "project_id" {
  type = string
}

variable "datasource_configuration" {

  type = any
  
}

variable "environment_id" {
  type = string
}



