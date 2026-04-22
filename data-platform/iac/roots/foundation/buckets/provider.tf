// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

// Aliased provider for explicit multi-region references
provider "aws" {

  alias  = "primary"
  region = var.REGION
}

// Default provider — used by bucket modules that don't specify a provider
provider "aws" {

  region = var.REGION
}
