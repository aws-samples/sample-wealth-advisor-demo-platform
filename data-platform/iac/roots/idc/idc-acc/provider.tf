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

provider "aws" {

  region = var.AWS_PRIMARY_REGION
}

# IAM Identity Center is account-scoped but the API must be queried via the
# region where the instance was created. The script discovers that region at
# apply time; we always include us-east-1 and us-west-2 as fallback aliases so
# Terraform can read the data source regardless of where the instance lives.
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

provider "aws" {
  alias  = "us_west_2"
  region = "us-west-2"
}
