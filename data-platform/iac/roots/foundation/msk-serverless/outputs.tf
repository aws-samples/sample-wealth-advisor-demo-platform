output "endpoint" {
  description = "IAM authentication bootstrap brokers"
  value       = aws_msk_serverless_cluster.cluster.bootstrap_brokers_sasl_iam
}

output "arn" {
  description = "The ARN of the MSK cluster"
  value       = aws_msk_serverless_cluster.cluster.arn
}

output "cluster_name" {
  description = "The name of the MSK cluster"
  value       = aws_msk_serverless_cluster.cluster.cluster_name
}

output "lambda_function_name" {
  description = "Name of the MSK producer Lambda function"
  value       = module.data_generator_lambda.function_name
}

output "lambda_function_arn" {
  description = "ARN of the MSK producer Lambda function"
  value       = module.data_generator_lambda.arn
}
