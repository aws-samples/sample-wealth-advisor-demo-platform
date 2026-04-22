// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

resource "aws_iam_role" "smus_domain_service_role" {

  name = var.smus_domain_service_role_name

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "datazone.amazonaws.com"
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
resource "aws_iam_role_policy_attachment" "service_role_policy" {

  role       = aws_iam_role.smus_domain_service_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/SageMakerStudioDomainServiceRolePolicy"
}

# Save the role name in SSM Parameter Store
resource "aws_ssm_parameter" "smus_domain_service_role_name" {

  name  = "/${var.APP}/${var.ENV}/smus_domain_service_role_name"
  type  = "SecureString"
  value = var.smus_domain_service_role_name
  key_id = data.aws_kms_key.ssm_kms_key.key_id

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = "SMUS Domain Pre-req"
  }
  overwrite = true
}

# Save the role ARN in SSM Parameter Store
resource "aws_ssm_parameter" "smus_domain_service_role_arn" {

  name = "/${var.APP}/${var.ENV}/smus_domain_service_role_arn"
  type = "SecureString"
  value = aws_iam_role.smus_domain_service_role.arn
  key_id = data.aws_kms_key.ssm_kms_key.key_id

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage = "SMUS Domain Pre-req"
  }
  overwrite = true
}
