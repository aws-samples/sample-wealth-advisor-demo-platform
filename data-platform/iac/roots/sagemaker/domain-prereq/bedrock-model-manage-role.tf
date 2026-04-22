// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

resource "aws_iam_role" "smus_domain_bedrock_model_manage_role" {

  name = var.smus_domain_bedrock_model_manage_role_name

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = ["sts:AssumeRole", "sts:SetContext"]
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
resource "aws_iam_role_policy_attachment" "bedrock_model_management_role_policy" {

  role       = aws_iam_role.smus_domain_bedrock_model_manage_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonDataZoneBedrockModelManagementPolicy"
}
