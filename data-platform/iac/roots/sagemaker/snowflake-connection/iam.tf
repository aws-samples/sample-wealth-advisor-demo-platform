// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

resource "aws_iam_role" "datazone_connection_lambda_exec_role" {

  name = "${var.APP}-${var.ENV}-lambda-datazone-conn-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_policy" "datazone_connection_lambda_exec_policy" {

  name        = "${var.APP}-${var.ENV}-lambda-datazone-conn-policy"
  description = "Policy for DataZone Connection Lambda"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Effect   = "Allow"
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Action   = "sts:AssumeRole"
        Effect   = "Allow"
        Resource = "arn:aws:iam::${var.AWS_ACCOUNT_ID}:role/datazone_usr_role_${local.producer_project_id}_${local.smus_producer_environment_id}"
      },
      {
        Action   = "sns:Publish"
        Effect   = "Allow"
        Resource = aws_sns_topic.datazone_connection_lambda_dlq_topic.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "datazone_connection_lambda_exec_attach" {

  role       = aws_iam_role.datazone_connection_lambda_exec_role.name
  policy_arn = aws_iam_policy.datazone_connection_lambda_exec_policy.arn
}
