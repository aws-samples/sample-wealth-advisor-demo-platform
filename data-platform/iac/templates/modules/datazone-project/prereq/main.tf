// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

# Create Datazone IAM role for Glue
resource "aws_iam_role" "glue" {
  name = "DataZoneGlueAccessRole-${data.aws_region.current.name}-${var.domain_id}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "datazone.amazonaws.com"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
          ArnEquals = {
            "aws:SourceArn" = "arn:aws:datazone:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:domain/${var.domain_id}"
          }
        }
      }
    ]
  })
}

# Create policy
data "aws_iam_policy" "glue" {
  name = "AmazonDataZoneGlueManageAccessRolePolicy"
}

resource "aws_iam_role_policy" "dataaccess_kms_policy" {
  name = "${var.APP}-${var.ENV}-datazone-accessing-policy"
  role = aws_iam_role.glue.id
  policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:Encrypt",
          "kms:GenerateDataKey"
        ]
        Resource = ["arn:aws:kms:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:*"]
      }
    ]
  })
}

# Attach Policy
resource "aws_iam_role_policy_attachment" "glue" {
  role       = aws_iam_role.glue.name
  policy_arn = data.aws_iam_policy.glue.arn
}

# Create Datazone IAM role for Provisisoning
resource "aws_iam_role" "datazone_provisioning" {
  name = "AmazonDataZoneProvisioning-${data.aws_caller_identity.current.account_id}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect : "Allow"
        Principal : {
          Service : "datazone.amazonaws.com"
        }
        Action : "sts:AssumeRole"
        Condition : {
          StringEquals : {
            "aws:SourceAccount" : data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })
}

# Add policy
data "aws_iam_policy" "datazone_provisioning" {
  name = "AmazonDataZoneRedshiftGlueProvisioningPolicy"
}

# Attach policy
resource "aws_iam_role_policy_attachment" "datazone_provisioning" {
  role       = aws_iam_role.datazone_provisioning.name
  policy_arn = data.aws_iam_policy.datazone_provisioning.arn
}


resource "aws_iam_role_policy" "datazone_kms_policy" {
  name = "${var.APP}-${var.ENV}-datazone-provisioning-policy"
  role = aws_iam_role.datazone_provisioning.id
  policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:Encrypt",
          "kms:GenerateDataKey"
        ]
        Resource = ["arn:aws:kms:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:*"]
      }
    ]
  })
}

# Create Datazone IAM role for Environment  
resource "aws_iam_role" "environment_role" {
  name = "DataZoneEnvironmentRole-${data.aws_region.current.name}-${var.domain_id}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "datazone.amazonaws.com"
        }
        Action = ["sts:AssumeRole", "sts:TagSession"]
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })
}

# Create policy
data "aws_iam_policy" "admin" {
  name = "AmazonDataZoneRedshiftGlueProvisioningPolicy"
}

# Attach policy
resource "aws_iam_role_policy_attachment" "environment_attachment" {
  role       = aws_iam_role.environment_role.name
  policy_arn = data.aws_iam_policy.admin.arn
}


# Get Blueprint Id
data "aws_datazone_environment_blueprint" "default_data_lake" {
  domain_id = var.domain_id
  name      = var.blue_print
  managed   = true
}

# Enable Datazone Datalake Blueprint 
resource "aws_datazone_environment_blueprint_configuration" "dz_datalake" {
  domain_id                = var.domain_id
  environment_blueprint_id = data.aws_datazone_environment_blueprint.default_data_lake.id
  manage_access_role_arn   = aws_iam_role.glue.arn
  provisioning_role_arn    = aws_iam_role.datazone_provisioning.arn
  enabled_regions          = ["${var.region}"]

  regional_parameters = {
    us-east-1 = {
      S3Location = var.DATALAKE_S3
    }
  }

}

resource "aws_ssm_parameter" "datalake_blueprint" {

  name        = "/${var.APP}/${var.ENV}/${var.domain_id}/datalake_blueprint_id"
  description = "The custom blueprint id"
  type        = "SecureString"
  value       = aws_datazone_environment_blueprint_configuration.dz_datalake.environment_blueprint_id
  key_id      = var.KMS_KEY

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage       = var.USAGE
  }
  overwrite = true
}

# Publish Datalake SSM Parameter
resource "aws_ssm_parameter" "custom_environment_role" {

  name        = "/${var.APP}/${var.ENV}/${var.domain_id}/custom_env_role"
  description = "The custom environment roled"
  type        = "SecureString"
  value       = aws_iam_role.environment_role.arn
  key_id      = var.KMS_KEY

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage       = var.USAGE
  }
  overwrite = true
}

# Enable Datazone Custom Blueprint
resource "awscc_datazone_environment_blueprint_configuration" "dz_custom" {
  domain_identifier                = var.domain_id
  enabled_regions                  = ["${var.region}"]
  environment_blueprint_identifier = "CustomAwsService"
  manage_access_role_arn           = aws_iam_role.glue.arn
  provisioning_role_arn            = aws_iam_role.datazone_provisioning.arn
}

# Publish Custom SSM Parameter
resource "aws_ssm_parameter" "custom_blueprint" {

  name        = "/${var.APP}/${var.ENV}/${var.domain_id}/custom_blueprint_id"
  description = "The custom blueprint id"
  type        = "SecureString"
  value       = awscc_datazone_environment_blueprint_configuration.dz_custom.environment_blueprint_id
  key_id      = var.KMS_KEY

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage       = var.USAGE
  }
  overwrite = true
}
