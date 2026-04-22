// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

locals {
  project = replace(var.project_name, " ", "-")
}

data "aws_ssm_parameter" "datazone_domain_id" {
  name = "/${var.APP}/${var.ENV}/smus_domain_id"
}

data "aws_ssm_parameter" "project_id" {
  name = "/${var.APP}/${var.ENV}/project-${local.project}"
}



   
