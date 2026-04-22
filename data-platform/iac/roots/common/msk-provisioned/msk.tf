// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

data "aws_kms_key" "msk_kms_key" {

  provider = aws.primary
  key_id   = "alias/${var.MSK_KMS_KEY_ALIAS}"
}

data "aws_kms_key" "s3_primary_key" {

  provider = aws.primary
  key_id   = "alias/${var.S3_PRIMARY_KMS_KEY_ALIAS}"
}

data "aws_kms_key" "s3_secondary_key" {

  provider = aws.secondary
  key_id   = "alias/${var.S3_SECONDARY_KMS_KEY_ALIAS}"
}

data "aws_kms_key" "ssm_kms_key" {

  provider = aws.primary
  key_id   = "alias/${var.SSM_KMS_KEY_ALIAS}"
}

data "aws_kms_key" "cloudwatch_kms_key" {

  provider = aws.primary
  key_id   = "alias/${var.CLOUDWATCH_KMS_KEY_ALIAS}"
}

resource "aws_cloudwatch_log_group" "log_group" {

  name              = "${var.APP}-${var.ENV}-msk-cloudwatch-log-group"
  retention_in_days = 365
  kms_key_id        = data.aws_kms_key.cloudwatch_kms_key.arn
}

module "log_bucket" {

  source = "../../../templates/modules/bucket"
  providers = {
    aws.primary   = aws.primary
    aws.secondary = aws.secondary
  }

  RESOURCE_PREFIX              = "${var.APP}-${var.ENV}-msk-logs"
  BUCKET_NAME_PRIMARY_REGION   = "primary"
  BUCKET_NAME_SECONDARY_REGION = "secondary"
  PRIMARY_CMK_ARN              = data.aws_kms_key.s3_primary_key.arn
  SECONDARY_CMK_ARN            = data.aws_kms_key.s3_secondary_key.arn
  APP                          = var.APP
  ENV                          = var.ENV
  USAGE                        = "msk-provisioned"
}

resource "aws_msk_cluster" "msk_cluster" {

  cluster_name           = "${var.APP}-${var.ENV}-provisioned-msk-cluster"
  kafka_version          = "3.7.x"
  number_of_broker_nodes = 3

  broker_node_group_info {
    
    instance_type = "kafka.m5.large"
    
    client_subnets = [
      local.PRIVATE_SUBNET1_ID,
      local.PRIVATE_SUBNET2_ID,
      local.PRIVATE_SUBNET3_ID,
    ]

    security_groups = [aws_security_group.provisioned_msk_primary.id]

    storage_info {
      ebs_storage_info {
        volume_size = 1000
      }
    }
  }

  encryption_info {
    encryption_at_rest_kms_key_arn = data.aws_kms_key.msk_kms_key.arn
  }

  client_authentication {
    sasl {
      iam = true
    }
  }

  logging_info {
    broker_logs {
      cloudwatch_logs {
        enabled   = true
        log_group = aws_cloudwatch_log_group.log_group.name
      }
      firehose {
        enabled = false
      }
      s3 {
        enabled = true
        bucket  = "${var.APP}-${var.ENV}-msk-logs-primary"
      }
    }
  }

  enhanced_monitoring = "PER_TOPIC_PER_BROKER"

  depends_on = [
    module.log_bucket
  ]
}

resource "aws_ssm_parameter" "msk_cluster" {

  name        = "/${var.APP}/${var.ENV}/msk-cluster"
  description = "The msk cluster arn"
  type        = "SecureString"
  value       = aws_msk_cluster.msk_cluster.arn
  key_id      = data.aws_kms_key.ssm_kms_key.arn
  overwrite = true
}

resource "aws_ssm_parameter" "msk_bootstrap_brokers" {

  name        = "/${var.APP}/${var.ENV}/msk-bootstrap-brokers"
  description = "The msk bootstrap brokers"
  type        = "SecureString"
  value       = aws_msk_cluster.msk_cluster.bootstrap_brokers_sasl_iam
  key_id      = data.aws_kms_key.ssm_kms_key.arn
  overwrite = true
}

