# TO DO: 
## How many messages we want to create with the test generator 
## Invoke lambda function every minute with eventbridge - started
## Lambda duration = 15 minutes

# Security group for Lambda
resource "aws_security_group" "lambda_sg" {
  name_prefix = "${var.APP}-${var.ENV}-msk-producer-lambda-sg-"
  description = "Security group for MSK producer Lambda"
  vpc_id      = local.VPC_ID

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }

  tags = {
    Name        = "${var.APP}-${var.ENV}-msk-producer-lambda-sg"
    Application = var.APP
    Environment = var.ENV
  }

  # Create the new SG before destroying the old one. This breaks the circular
  # dependency where Lambda ENIs hold the old SG, blocking deletion, while the
  # new SG can't be created until the old one is gone.
  lifecycle {
    create_before_destroy = true
  }
}

# Create IAM policy for Lambda to access MSK, SSM, and Secrets Manager
resource "aws_iam_policy" "lambda_msk_policy" {
  name        = "${var.APP}-${var.ENV}-msk-producer-lambda-policy"
  description = "Policy for MSK producer Lambda"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kafka:DescribeCluster",
          "kafka:GetBootstrapBrokers"
        ]
        Resource = "arn:aws:kafka:${var.AWS_PRIMARY_REGION}:${data.aws_caller_identity.current.account_id}:cluster/${aws_msk_serverless_cluster.cluster.cluster_name}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "kafka:ListClusters"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "kafka-cluster:Connect",
          "kafka-cluster:AlterCluster",
          "kafka-cluster:DescribeCluster"
        ]
        Resource = "arn:aws:kafka:${var.AWS_PRIMARY_REGION}:${data.aws_caller_identity.current.account_id}:cluster/${aws_msk_serverless_cluster.cluster.cluster_name}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "kafka-cluster:*Topic*",
          "kafka-cluster:WriteData",
          "kafka-cluster:ReadData"
        ]
        Resource = "arn:aws:kafka:${var.AWS_PRIMARY_REGION}:${data.aws_caller_identity.current.account_id}:topic/${aws_msk_serverless_cluster.cluster.cluster_name}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "kafka-cluster:AlterGroup",
          "kafka-cluster:DescribeGroup"
        ]
        Resource = "arn:aws:kafka:${var.AWS_PRIMARY_REGION}:${data.aws_caller_identity.current.account_id}:group/${aws_msk_serverless_cluster.cluster.cluster_name}r/*"
      },
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ]
        Resource = [
          "arn:aws:ssm:${var.AWS_PRIMARY_REGION}:${data.aws_caller_identity.current.account_id}:parameter/${var.APP}/${var.ENV}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          "arn:aws:secretsmanager:${var.AWS_PRIMARY_REGION}:${data.aws_caller_identity.current.account_id}:secret:${var.APP}-${var.ENV}-msk-endpoint*"
        ]
      }
    ]
  })

  #checkov:skip=CKV_AWS_355: "Ensure no IAM policies documents allow '*' as a statement's resource for restrictable actions": "kafka:ListClusters does not support resource-level permissions. All other actions are resource-scoped."
}

# Create the Lambda layer for dependencies
resource "aws_lambda_layer_version" "dependencies_layer" {
  layer_name          = "${var.APP}-${var.ENV}-msk-producer-dependencies"
  description         = "Dependencies for MSK producer lambda"
  filename            = "${path.module}/data-generator/dependencies_layer.zip"
  source_code_hash    = filebase64sha256("${path.module}/data-generator/dependencies_layer.zip")
  compatible_runtimes = ["python3.12"]

  # The zip is rebuilt on every CodeBuild run (pip re-downloads packages with
  # different timestamps/metadata), producing a different hash each time even
  # when the actual dependencies haven't changed. Ignoring source_code_hash
  # and filename prevents a new layer version from being published on every run,
  # which would cascade into lambda_sg replacement and a 45-minute ENI cleanup.
  # To force a layer update when dependencies genuinely change: terraform taint aws_lambda_layer_version.dependencies_layer
  lifecycle {
    ignore_changes = [source_code_hash, filename]
  }
}

data "archive_file" "generator_lambda_zip" {

  type        = "zip"
  source_dir  = "${path.module}/data-generator"
  excludes    = ["lambda-packages"]
  output_path = "${path.module}/lambda_function.zip"
}

# Create the data generator lambda function
module "data_generator_lambda" {
  source = "../../../templates/modules/lambda"

  region = var.AWS_PRIMARY_REGION
  function_name = "${var.APP}-${var.ENV}-msk-producer-lambda"
  handler_name  = "mskProducer.lambda_handler"
  description   = "Lambda function to generate financial data events"
  runtime       = "python3.12"
  resource_policies = [
    aws_iam_policy.lambda_msk_policy.arn,
    "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
  ]
  code_archive      = data.archive_file.generator_lambda_zip.output_path
  code_archive_hash = data.archive_file.generator_lambda_zip.output_base64sha256

  # Add the dependencies layer
  layer_arns = [aws_lambda_layer_version.dependencies_layer.arn]

  # Pass VPC configuration 
  subnet_ids = [
    local.PRIVATE_SUBNET1_ID,
    local.PRIVATE_SUBNET2_ID,
    local.PRIVATE_SUBNET3_ID
  ]
  security_group_ids = [aws_security_group.lambda_sg.id]

  # Pass environment variables 
  environment_variables = {
    LOG_LEVEL           = "INFO"
    APP_NAME            = var.APP
    ENV_NAME            = var.ENV
    GLOBAL_MSK_ENDPOINT = aws_secretsmanager_secret.msk_endpoint_primary.id
    MSK_SSM_NAME        = aws_ssm_parameter.msk_cluster_arn_primary.name
  }

  # Lambda configuration
  memory_size = 512
  timeout     = 900
}
