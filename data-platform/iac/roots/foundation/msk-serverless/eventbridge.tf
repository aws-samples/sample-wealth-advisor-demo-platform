# # EventBridge rule to trigger the data generator lambda every minute
resource "aws_cloudwatch_event_rule" "data_generator_schedule" {
  name                = "data-generator-schedule"
  description         = "Triggers the data generator lambda every minute"
  schedule_expression = "rate(15 minutes)"
  state               = "DISABLED"
}

# # Set the lambda function as the target for the EventBridge rule
resource "aws_cloudwatch_event_target" "stocks_data_generator_target" {
  rule      = aws_cloudwatch_event_rule.data_generator_schedule.name
  target_id = "stocks-data-generator-target"
  arn       = module.data_generator_lambda.arn
  input = jsonencode({
    body = "{\"topic\":\"intraday-source-topic\",\"duration\":15,\"parallel\":1,\"execution\":\"process\",\"sleep\":1}"
  })
}

resource "aws_cloudwatch_event_target" "trade_data_generator_target" {
  rule      = aws_cloudwatch_event_rule.data_generator_schedule.name
  target_id = "trade-data-generator-target"
  arn       = module.data_generator_lambda.arn
  input = jsonencode({
    body = "{\"topic\":\"trade-topic\",\"duration\":15,\"parallel\":1,\"execution\":\"process\",\"sleep\":1}"
  })
}

# # Grant EventBridge permission to invoke the lambda function
resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = module.data_generator_lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.data_generator_schedule.arn
}
