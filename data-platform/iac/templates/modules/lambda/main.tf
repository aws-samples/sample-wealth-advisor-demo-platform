
#
# IAM role for the lambda function
#
data "aws_iam_policy_document" "lambda_role_policy" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "iam_for_lambda" {
  name_prefix        = "${var.function_name}-role-"
  assume_role_policy = data.aws_iam_policy_document.lambda_role_policy.json
}

#
# Attaching AWSLambdaBasicExecutionRole and AWSXrayWriteOnlyAccess policies
# to the Lambda role (AWS Managed Policy)
#
resource "aws_iam_role_policy_attachment" "lambda_execution_role_policy" {
  role       = aws_iam_role.iam_for_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "xray_role_policy" {
  role       = aws_iam_role.iam_for_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/AWSXrayWriteOnlyAccess"
}

#
# Resource access policies
#
resource "aws_iam_role_policy_attachment" "lambda_policies" {
  count      = length(var.resource_policies)
  role       = aws_iam_role.iam_for_lambda.id
  policy_arn = var.resource_policies[count.index]
}

#
# Log group for the function
#
module "logs" {
  source   = "../cloudwatch_log_group"
  name     = "/aws/lambda/${var.function_name}"
  roles    = [aws_iam_role.iam_for_lambda.arn]
  services = ["logs.${var.region}.amazonaws.com"]
}

#
# Lambda function
#
resource "aws_lambda_function" "function" {
  #Skipping checkov checks
  #checkov:skip=CKV_AWS_116: "Ensure that AWS Lambda function is configured for a Dead Letter Queue(DLQ)"
  #checkov:skip=CKV_AWS_173: "Check encryption settings for Lambda environmental variable"
  #checkov:skip=CKV_AWS_272: "Ensure AWS Lambda function is configured to validate code-signing"
  depends_on    = [module.logs]
  function_name = var.function_name
  description   = var.description
  role          = aws_iam_role.iam_for_lambda.arn
  publish       = true
  handler       = var.handler_name
  runtime       = var.runtime
  timeout       = var.timeout
  memory_size   = var.memory_size
  layers        = var.layer_arns
  filename = var.code_archive == null ? "${path.module}/code.zip" : var.code_archive
  source_code_hash = var.code_archive == null ? filebase64sha256("code.zip") : var.code_archive_hash

  tracing_config {
    mode = "Active"
  }

  reserved_concurrent_executions = -1
  environment {
    variables = var.environment_variables
  }

  vpc_config {
    # If the list of security group ids and subnets are empty,
    # this property is effectively ignored
    subnet_ids         = var.subnet_ids
    security_group_ids = var.security_group_ids
  }
}

#
# Test alias for the function
#
resource "aws_lambda_alias" "test_alias" {
  name             = "test"
  description      = "Test version of the function"
  function_name    = aws_lambda_function.function.arn
  function_version = aws_lambda_function.function.version

  lifecycle {
    ignore_changes = [
      # Ignore changes to function version as those will be managed by the lambda function build
      function_version
    ]
  }
}

#
# Prod alias for the function
#
resource "aws_lambda_alias" "prod_alias" {
  name             = "prod"
  description      = "Prod version of the function"
  function_name    = aws_lambda_function.function.arn
  function_version = aws_lambda_function.function.version

  lifecycle {
    ignore_changes = [
      # Ignore changes to function version as those will be managed by the lambda function build
      function_version
    ]
  }
}