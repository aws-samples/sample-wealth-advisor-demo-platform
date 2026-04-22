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

variable "project_id" {
  type = string
}

variable "account_id" {
  type = string
}

variable "region" {
  type = string
}

variable "description" {  
  type = string
}

variable "env_name" {  
  type = string
}

variable "env_actions" {

  type  = any
}

variable "environment_role" {
  type = string
}

variable "environment_blueprint_id" {
  
  type = string
}




