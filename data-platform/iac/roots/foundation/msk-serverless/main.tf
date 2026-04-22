
resource "aws_msk_serverless_cluster" "cluster" {
  cluster_name = "${var.APP}-${var.ENV}-msk-cluster"
  client_authentication {
    sasl {
      iam {
        enabled = true
      }
    }
  }
  vpc_config {
    subnet_ids = [local.PRIVATE_SUBNET1_ID, local.PRIVATE_SUBNET2_ID, local.PRIVATE_SUBNET3_ID]
    security_group_ids = [aws_security_group.msk_primary.id]
  }
}

resource "aws_ssm_parameter" "msk_cluster_arn_primary" {
  name      = "/${var.APP}/${var.ENV}/msk/cluster_arn"
  type      = "String"
  value     = aws_msk_serverless_cluster.cluster.arn
  overwrite = true
  tags = {
    Environment = var.ENV
    Application = var.APP
    Usage       = "msk"
  }
}

resource "aws_secretsmanager_secret" "msk_endpoint_primary" {
  name     = "${var.APP}-${var.ENV}-msk-endpoint"
  recovery_window_in_days = 0 //change it for production
  tags = {
    Environment = var.ENV
    Application = var.APP
    Usage       = "msk"
  }
}

resource "aws_secretsmanager_secret_version" "msk_endpoint_primary" {
  secret_id     = aws_secretsmanager_secret.msk_endpoint_primary.id
  secret_string = aws_msk_serverless_cluster.cluster.bootstrap_brokers_sasl_iam
}