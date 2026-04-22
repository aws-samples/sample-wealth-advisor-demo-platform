// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

data "aws_ssm_parameter" "smus_domain_id" {

  name = "/${var.APP}/${var.ENV}/smus_domain_id"
}

locals {
  SMUS_DOMAIN_ID  = data.aws_ssm_parameter.smus_domain_id.value
}
