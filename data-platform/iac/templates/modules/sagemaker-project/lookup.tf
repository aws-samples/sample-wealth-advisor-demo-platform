// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

data "aws_ssm_parameter" "smus_domain_id" {

  name = "/${var.APP}/${var.ENV}/smus_domain_id"
}

data "aws_ssm_parameter" "smus_profile_4" {

  name = "/${var.APP}/${var.ENV}/project_profile_4"
}

data "aws_ssm_parameter" "smus_lambda_layer_arn" {

  name = "/${var.APP}/${var.ENV}/smus_lambda_layer_arn"
}

data "aws_ssm_parameter" "smus_lambda_service_role_name" {

  name = "/${var.APP}/${var.ENV}/smus_lambda_service_role_name"
}

data "aws_ssm_parameter" "user_mappings" {
  name = "/${var.APP}/${var.ENV}/identity-center/users"
}



   
