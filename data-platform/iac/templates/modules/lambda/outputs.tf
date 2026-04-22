output "arn" {
  value       = aws_lambda_function.function.arn
  description = "ARN of the lambda function"
}

output "invocation_arn" {
  value       = aws_lambda_function.function.invoke_arn
  description = "Invocation ARN of the lambda function"
}

output "function_name" {
  value = aws_lambda_function.function.function_name
  description = "Lambda function name"
}

output "function_version" {
  value = aws_lambda_function.function.version
  description = "Lambda function version"
}

