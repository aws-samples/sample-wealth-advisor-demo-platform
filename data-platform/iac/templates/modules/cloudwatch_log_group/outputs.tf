#
# Create outputs here
#
output "arn" {
  description = "ARN of the cloudwatch log group"
  value       = aws_cloudwatch_log_group.log.arn
}

output "name" {
  description = "Name of the cloudwatch log group"
  value       = aws_cloudwatch_log_group.log.name
}