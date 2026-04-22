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

variable "project_name" {
  type = string
}

variable "project_description" {
  type = string
}

variable "project_owner" {
  type = string
}

variable "glossary_terms" {
  type = any
  default = null
}





