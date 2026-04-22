resource "aws_s3_bucket" "lambda_bucket" {
  bucket = var.LAMBDA_BUCKET

  #checkov:skip=CKV_AWS_18: "Ensure the S3 bucket has access logging enabled": "Deployment-time utility bucket for Lambda zip only. Low risk, no sensitive data."
}

resource "aws_s3_bucket_policy" "lambda_bucket_policy" {
  bucket = aws_s3_bucket.lambda_bucket.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:user/datapipeline" }
      Action    = "s3:*"
      Resource  = [
        aws_s3_bucket.lambda_bucket.arn,
        "${aws_s3_bucket.lambda_bucket.arn}/*"
      ]
    }]
  })
}

resource "aws_s3_object" "lambda_layer_zip" {
  bucket = aws_s3_bucket.lambda_bucket.id
  key    = "lambda_layer.zip"
  source = "${path.module}/lambda_layer.zip"
}

resource "aws_lambda_layer_version" "mfa_disabler_layer" {
  layer_name          = "${var.APP}-${var.ENV}-mfa-disabler-layer"
  s3_bucket           = aws_s3_bucket.lambda_bucket.id
  s3_key              = aws_s3_object.lambda_layer_zip.key
  compatible_runtimes = ["python3.9"]

  depends_on = [aws_s3_object.lambda_layer_zip]
}

data "archive_file" "disable_mfa_zip" {
  type        = "zip"
  source_file = "${path.module}/lambda/disable_mfa.py"
  output_path = "${path.module}/disable_mfa.zip"
}

resource "aws_s3_object" "disable_mfa_zip" {
  bucket = aws_s3_bucket.lambda_bucket.id
  key    = "disable_mfa.zip"
  source = data.archive_file.disable_mfa_zip.output_path
}

resource "aws_iam_role" "lambda_exec" {
  name = "${var.APP}-${var.ENV}-lambda-disable-mfa-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = {
        Service = "lambda.amazonaws.com"
      },
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "basic_lambda" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_permissions" {
  name = "${var.APP}-${var.ENV}-disable-mfa-lambda-permissions"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "sso:ListInstances",
          "sso:UpdateSsoConfiguration",
          "sso:GetSsoConfiguration"
        ],
        Resource = "*"
      },
      {
        Effect = "Allow",
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Resource = "arn:aws:logs:*:*:*"
      },
    ]
  })

  #checkov:skip=CKV_AWS_355: "Ensure no IAM policies documents allow '*' as a statement's resource for restrictable actions": "SSO actions do not support resource-level permissions. Actions already tightened to minimum required."
  #checkov:skip=CKV_AWS_290: "Ensure IAM policies does not allow write access without constraints": "sso:UpdateSsoConfiguration requires Resource '*'. Action already tightened to minimum required."
  #checkov:skip=CKV_AWS_289: "Ensure IAM policies does not allow permissions management / resource exposure without constraints": "sso:UpdateSsoConfiguration requires Resource '*'. Action already tightened to minimum required."
}

resource "aws_lambda_function" "mfa_disabler" {
  function_name = "${var.APP}-${var.ENV}-mfa-disabler"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "disable_mfa.lambda_handler"
  runtime       = "python3.9"
  timeout       = 60

  s3_bucket = aws_s3_bucket.lambda_bucket.id
  s3_key    = aws_s3_object.disable_mfa_zip.key

  layers = [aws_lambda_layer_version.mfa_disabler_layer.arn]

  depends_on = [aws_s3_object.disable_mfa_zip, aws_lambda_layer_version.mfa_disabler_layer]
}

resource "null_resource" "invoke_mfa_disabler" {
  depends_on = [aws_lambda_function.mfa_disabler]

  provisioner "local-exec" {
    command = <<EOT
      aws lambda invoke \
        --function-name ${aws_lambda_function.mfa_disabler.function_name} \
        --invocation-type RequestResponse \
        --cli-binary-format raw-in-base64-out \
        --region ${var.AWS_PRIMARY_REGION} \
        mfa_response.json
    EOT
  }

  triggers = {
    always_run = timestamp()
  }
}