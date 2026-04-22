// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

resource "random_string" "random_role_prefix" {

    length  = 10
    special = false
    upper   = false
    lower   = true
    numeric = true

    keepers = {
      trigger = timestamp()
    }
}
# "${var.smus_domain_provisioning_role_name}-${random_string.random_role_prefix.result}"

# Create SageMaker Provisioning Role
resource "aws_iam_role" "smus_sm_provisioning_role" {

  name = "${var.smus_domain_provisioning_role_name}-${local.account_id}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = [
            "datazone.amazonaws.com", 
            "lambda.amazonaws.com"
          ]
        }
        Condition = {
          "StringEquals": {
            "aws:SourceAccount": local.account_id
          }
        }        
      }
    ]
  })
}

# Attach necessary policies to it
resource "aws_iam_role_policy_attachment" "sm_provisioning_role_sm_studio_policy" {

  role       = aws_iam_role.smus_sm_provisioning_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/SageMakerStudioProjectProvisioningRolePolicy"
}

# Attach KMS policy to it
resource "aws_iam_role_policy" "sm_provisioning_role_kms_policy" {

  name = "sm-provisioning-role-kms-policy"
  role = aws_iam_role.smus_sm_provisioning_role.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:Encrypt",
          "kms:GenerateDataKey",
          "kms:GenerateDataKeyPair",
          "kms:GenerateDataKeyPairWithoutPlaintext",
          "kms:GenerateDataKeyWithoutPlaintext",
          "kms:ReEncryptFrom"
        ]
        Resource = data.aws_kms_key.domain_kms_key.arn
      },
      {
        Effect = "Allow"
        Action = [
          "kms:CreateGrant",
          "kms:ReEncryptTo"
        ]
        Resource = data.aws_kms_key.domain_kms_key.arn
        Condition = {
          Bool = {
            "kms:GrantIsForAWSResource" = "true"
          }
        }
      }
    ]
  })
}

# Attach necessary policies to it
resource "aws_iam_role_policy_attachment" "sm_provisioning_role_lambda_policy" {

  role       = aws_iam_role.smus_sm_provisioning_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Save the role name in SSM Parameter Store
resource "aws_ssm_parameter" "smus_domain_provisioning_role_name" {

  name  = "/${var.APP}/${var.ENV}/smus_domain_provisioning_role_name"
  type  = "SecureString"
  value = aws_iam_role.smus_sm_provisioning_role.name
  key_id = data.aws_kms_key.ssm_kms_key.key_id

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = "SMUS Domain Pre-req"
  }
  overwrite = true
}

# Save the role ARN in SSM Parameter Store
resource "aws_ssm_parameter" "smus_domain_provisioning_role_arn" {

  name = "/${var.APP}/${var.ENV}/smus_domain_provisioning_role_arn"
  type = "SecureString"
  value = aws_iam_role.smus_sm_provisioning_role.arn
  key_id = data.aws_kms_key.ssm_kms_key.key_id

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = "SMUS Domain Pre-req"
  }
  overwrite = true
}
