data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

data "aws_kms_key" "ssm_kms_key" {
  key_id = "alias/${var.SSM_KMS_KEY_ALIAS}"
}


data "aws_ssm_parameter" "vpc_id" {
  name            = "/${var.APP}/${var.ENV}/vpc_id"
  with_decryption = true
}

data "aws_ssm_parameter" "vpc_private_subnet_ids" {
  name            = "/${var.APP}/${var.ENV}/vpc_private_subnet_ids"
  with_decryption = true
}

data "aws_vpc" "vpc" {
  id = data.aws_ssm_parameter.vpc_id.value
}

data "aws_ssm_parameter" "vpc_security_group" {
  name            = "/${var.APP}/${var.ENV}/vpc-sg"
  with_decryption = true
}

data "aws_ssm_parameter" "vpc_public_subnet_ids" {
  name            = "/${var.APP}/${var.ENV}/vpc_public_subnet_ids"
  with_decryption = true
}


locals {
  VPC_ID             = data.aws_ssm_parameter.vpc_id.value
  PRIVATE_SUBNET1_ID = split(",", data.aws_ssm_parameter.vpc_private_subnet_ids.value)[0]
  PRIVATE_SUBNET2_ID = split(",", data.aws_ssm_parameter.vpc_private_subnet_ids.value)[1]
  PRIVATE_SUBNET3_ID = split(",", data.aws_ssm_parameter.vpc_private_subnet_ids.value)[2]
  PUBLIC_SUBNET1_ID  = split(",", data.aws_ssm_parameter.vpc_public_subnet_ids.value)[0]
  PUBLIC_SUBNET2_ID  = split(",", data.aws_ssm_parameter.vpc_public_subnet_ids.value)[1]
  PUBLIC_SUBNET3_ID  = split(",", data.aws_ssm_parameter.vpc_public_subnet_ids.value)[2]
  VPC_SECURITY_GROUP = data.aws_ssm_parameter.vpc_security_group.value
}
