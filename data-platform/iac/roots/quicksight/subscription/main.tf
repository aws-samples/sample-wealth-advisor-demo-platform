// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

terraform {
  required_version = ">= 1.4.2"
}

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

locals {
  tags = {
    "App" = var.APP
    "Env" = var.ENV
  }
}


