// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

data "aws_kms_key" "domain_kms_key" {

  provider = aws.primary
  key_id   = "alias/${var.DOMAIN_KMS_KEY_ALIAS}"
}

# Create the domain execution IAM role
resource "aws_iam_role" "smus_domain_execution_role" {

  name = var.smus_domain_execution_role_name

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = ["sts:AssumeRole", "sts:TagSession", "sts:SetContext"]
        Effect = "Allow"
        Principal = {
          Service = "datazone.amazonaws.com"
        }
        Condition = {
          "ForAllValues:StringLike": {
            "aws:TagKeys": "datazone*"
          },
          "StringEquals": {
            "aws:SourceAccount": local.account_id
          }
        }
      }
    ]
  })
}

# Attach necessary policies to it
resource "aws_iam_role_policy_attachment" "execution_role_policy" {

  role       = aws_iam_role.smus_domain_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/SageMakerStudioDomainExecutionRolePolicy"
}

# Attach the KMS key policy to the role
resource "aws_iam_role_policy" "execution_role_kms_key_policy" {

  name = "smus_domain_execution_role_kms_key_policy"
  role = aws_iam_role.smus_domain_execution_role.name

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

# Save the role name in SSM Parameter Store
resource "aws_ssm_parameter" "smus_domain_execution_role_name" {

  name  = "/${var.APP}/${var.ENV}/smus_domain_execution_role_name"
  type  = "SecureString"
  value = var.smus_domain_execution_role_name
  key_id = data.aws_kms_key.ssm_kms_key.key_id

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = "SMUS Domain Pre-req"
  }
  overwrite = true
}

# Save the role ARN in SSM Parameter Store
resource "aws_ssm_parameter" "smus_domain_execution_role_arn" {

  name = "/${var.APP}/${var.ENV}/smus_domain_execution_role_arn"
  type = "SecureString"
  value = aws_iam_role.smus_domain_execution_role.arn
  key_id = data.aws_kms_key.ssm_kms_key.key_id

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = "SMUS Domain Pre-req"
  }
  overwrite = true
}
