// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

locals {
  layer_path        = "layers"
  layer_zip_name    = "layer.zip"
  layer_name        = "datazone_lambda_layer"
  requirements_name = "requirements.txt"
  requirements_path = "${path.module}/${local.layer_path}/${local.requirements_name}"
}

data "aws_kms_key" "ssm_kms_key" {

  key_id   = "alias/${var.SSM_KMS_KEY_ALIAS}"
}

data "aws_iam_policy_document" "trust_policy" {

  statement {
    sid    = ""
    effect = "Allow"

    actions = [
      "sts:AssumeRole",
      "sts:TagSession",
    ]

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = ["${local.account_id}"]
    }

    condition {
      test     = "ForAllValues:StringLike"
      variable = "aws:TagKeys"
      values   = ["datazone*"]
    }

    principals {
      type = "Service"

      identifiers = [
        "lambda.amazonaws.com",
        "datazone.amazonaws.com",
      ]
    }
  }

  statement {
    sid     = ""
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${local.account_id}:root"]
    }
  }
}

# Create IAM role for lambda execution
resource "aws_iam_role" "datazone_lambda_role" {

  name = "DatazoneLambdaExecutionRole"
  assume_role_policy = data.aws_iam_policy_document.trust_policy.json
}

# Create IAM policy for lambda execution
resource "aws_iam_role_policy" "execution_role_kms_key_policy" {

  name = "lambda_execution_role_kms_key_policy"
  role = aws_iam_role.datazone_lambda_role.name

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
        Resource = ["arn:aws:kms:${var.AWS_PRIMARY_REGION}:${local.account_id}:*"]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:CreateGrant",
          "kms:ReEncryptTo"
        ]
        Resource = ["arn:aws:kms:${var.AWS_PRIMARY_REGION}:${local.account_id}:*"]
        Condition = {
          Bool = {
            "kms:GrantIsForAWSResource" = "true"
          }
        }
      }
    ]
  })

  #checkov:skip=CKV_AWS_289: "Ensure IAM policies does not allow permissions management / resource exposure without constraints": "Skipping this for simplicity"
  #checkov:skip=CKV_AWS_290: "Ensure IAM policies does not allow write access without constraints": "Skipping this for simplicity"
}

# Attach AmazonDataZoneFullAccess managed policy
resource "aws_iam_role_policy_attachment" "datazone_policy" {

  role       = aws_iam_role.datazone_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonDataZoneFullAccess"
}

# Attach AWSLambdaBasicExecutionRole managed policy
resource "aws_iam_role_policy_attachment" "lambda_basic_policy" {

  role       = aws_iam_role.datazone_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Attach IAMReadOnlyAccess managed policy
resource "aws_iam_role_policy_attachment" "iam_basic_policy" {

  role       = aws_iam_role.datazone_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/IAMReadOnlyAccess"
}

#create zip file from requirements.txt. Triggers only when the file is updated
resource "null_resource" "lambda_layer" {

  triggers = {
     id = timestamp()
  }
  # the command to install python and dependencies to the machine and zips
  provisioner "local-exec" {
    command = <<EOT
      cd ${local.layer_path}
      mkdir python
      echo ${local.requirements_name}
      pip3 install -r ${local.requirements_name} -t python/
      zip -r ${local.layer_zip_name} python/
      rm -Rf python
    EOT
  }
}

# upload zip file to s3
resource "aws_s3_object" "lambda_layer_zip" {

  bucket     = var.CFN_DEPLOY_BUCKET
  key        = "lambda_layers/${local.layer_zip_name}"
  source     = "${local.layer_path}/${local.layer_zip_name}"
  depends_on = [null_resource.lambda_layer] # triggered only if the zip file is created
}

# create lambda layer from s3 object
resource "aws_lambda_layer_version" "lambda_layer" {

  s3_bucket           = var.CFN_DEPLOY_BUCKET
  s3_key              = aws_s3_object.lambda_layer_zip.key
  layer_name          = local.layer_name
  compatible_runtimes = ["python3.10"]
  skip_destroy        = true
  depends_on          = [aws_s3_object.lambda_layer_zip] # triggered only if the zip file is uploaded to the bucket
}

# Save the role name in SSM Parameter Store
resource "aws_ssm_parameter" "smus_lambda_execution_role_name" {

  name  = "/${var.APP}/${var.ENV}/smus_lambda_service_role_name"
  type  = "SecureString"
  value = aws_iam_role.datazone_lambda_role.arn
  key_id = data.aws_kms_key.ssm_kms_key.id

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage       = "SMUS Domain project"
  }

  depends_on = [ aws_iam_role.datazone_lambda_role ]
  overwrite = true
}

# Save the lambda Layer ARN in SSM Parameter Store
resource "aws_ssm_parameter" "smus_lambda_layer_arn" {

  name = "/${var.APP}/${var.ENV}/smus_lambda_layer_arn"
  type = "SecureString"
  value = aws_lambda_layer_version.lambda_layer.arn
  key_id = data.aws_kms_key.ssm_kms_key.id
  
  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage       = "SMUS Domain Project"
  }

  depends_on = [ aws_lambda_layer_version.lambda_layer ]
  overwrite = true
}
