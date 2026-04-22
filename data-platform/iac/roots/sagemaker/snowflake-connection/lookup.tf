// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

data "aws_ssm_parameter" "smus_domain_id" {

  name = "/${var.APP}/${var.ENV}/smus_domain_id"
}

data "aws_ssm_parameter" "sagemaker_vpc_private_subnet_ids" {

  name = "/${var.APP}/${var.ENV}/vpc_private_subnet_ids"
}

data "aws_ssm_parameter" "smus_projects_bucket_s3_url" {

  name = "/${var.APP}/${var.ENV}/smus_projects_bucket_s3_url"
}

data "aws_ssm_parameter" "smus_producer_environment_id" {

  name = "/${var.APP}/${var.ENV}/sagemaker/producer/tooling-env-id"
}

data "aws_ssm_parameter" "smus_producer_security_group" {

  name = "/${var.APP}/${var.ENV}/sagemaker/producer/security-group"
}

data "aws_ssm_parameter" "smus_producer_project_id" {

  name = "/${var.APP}/${var.ENV}/sagemaker/producer/id"
}

data "aws_kms_key" "secrets_manager_kms_key" {

  key_id = "alias/${var.SECRETS_MANAGER_KMS_KEY_ALIAS}"
}

data "aws_kms_key" "ssm_kms_key" {

  key_id   = "alias/${var.SSM_KMS_KEY_ALIAS}"
}
