// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

terraform {
  required_version = ">= 1.4.2"
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

data "aws_ssm_parameter" "redshift_env_id" {
  name = "/${var.APP}/${var.ENV}/sagemaker/producer/redshift-env-id"
}

data "aws_redshiftserverless_workgroup" "producer" {
  workgroup_name = "redshift-serverless-workgroup-${data.aws_ssm_parameter.redshift_env_id.value}"
}

data "external" "redshift_secret_arn" {
  program = ["bash", "-c", "aws redshift-serverless get-namespace --namespace-name redshift-serverless-namespace-${data.aws_ssm_parameter.redshift_env_id.value} --region ${var.AWS_PRIMARY_REGION} --query '{arn: namespace.adminPasswordSecretArn}' --output json"]
}

data "aws_secretsmanager_secret_version" "redshift_admin" {
  secret_id = data.external.redshift_secret_arn.result.arn
}

data "aws_ssm_parameter" "security_group" {
  name = "/${var.APP}/${var.ENV}/sagemaker/producer/security-group"
}

locals {
  tags = {
    "App" = var.APP
    "Env" = var.ENV
  }

  redshift_endpoint = data.aws_redshiftserverless_workgroup.producer.endpoint[0].address
  redshift_creds    = jsondecode(data.aws_secretsmanager_secret_version.redshift_admin.secret_string)
  security_group_id = data.aws_ssm_parameter.security_group.value
  subnet_ids        = data.aws_redshiftserverless_workgroup.producer.subnet_ids
}
