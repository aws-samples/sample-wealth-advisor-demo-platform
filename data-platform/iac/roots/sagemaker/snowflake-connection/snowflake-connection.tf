// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

locals {

  smus_domain_id               = data.aws_ssm_parameter.smus_domain_id.value
  producer_project_id          = data.aws_ssm_parameter.smus_producer_project_id.value
  smus_producer_environment_id = data.aws_ssm_parameter.smus_producer_environment_id.value
  smus_producer_security_group = data.aws_ssm_parameter.smus_producer_security_group.value

  selected_subnet_id       = try(split(",", data.aws_ssm_parameter.sagemaker_vpc_private_subnet_ids.value)[0], null)
  athena_spill_bucket_name = replace(data.aws_ssm_parameter.smus_projects_bucket_s3_url.value, "s3://", "")
  athena_spill_prefix_path = "${local.smus_domain_id}/${local.producer_project_id}/dev/sys/athena"
}

data "aws_subnet" "selected_subnet_info" {

  id = local.selected_subnet_id
}

locals {

  selected_availability_zone = local.selected_subnet_id == null ? null : data.aws_subnet.selected_subnet_info.availability_zone

  datazone_cli_input_json_payload = jsonencode({
    name                  = var.SNOWFLAKE_CONNECTION_NAME
    environmentIdentifier = local.smus_producer_environment_id
    props = {
      glueProperties = {
        glueConnectionInput = {
          name           = var.SNOWFLAKE_CONNECTION_NAME
          connectionType = "SNOWFLAKE"
          connectionProperties = {
            HOST      = var.SNOWFLAKE_HOST
            PORT      = var.SNOWFLAKE_PORT
            WAREHOUSE = var.SNOWFLAKE_WAREHOUSE
            DATABASE  = var.SNOWFLAKE_DATABASE
            SCHEMA    = var.SNOWFLAKE_SCHEMA
            ROLE_ARN  = "arn:aws:iam::${var.AWS_ACCOUNT_ID}:role/datazone_usr_role_${local.producer_project_id}_${local.smus_producer_environment_id}"
          }
          physicalConnectionRequirements = {
            availabilityZone    = local.selected_availability_zone
            securityGroupIdList = [local.smus_producer_security_group]
            subnetId            = local.selected_subnet_id
          }
          authenticationConfiguration = {
            authenticationType = "BASIC"
            secretArn          = aws_secretsmanager_secret.snowflake_credentials_secret.arn
          }
          validateForComputeEnvironments = ["SPARK", "ATHENA"]
          athenaProperties = {
            spill_bucket = local.athena_spill_bucket_name
            spill_prefix = local.athena_spill_prefix_path
          }
        }
      }
    }
  })
}

resource "aws_secretsmanager_secret" "snowflake_credentials_secret" {

  name                    = "${var.APP}-${var.ENV}-snowflake-credentials"
  recovery_window_in_days = 0
  description             = "Credentials for SageMaker Lakehouse Snowflake connection for Producer project ${var.APP}-${var.ENV}"
  kms_key_id              = data.aws_kms_key.secrets_manager_kms_key.id

  #checkov:skip=CKV2_AWS_57: "Ensure Secrets Manager secrets should have automatic rotation enabled": "Skipping for simplicity"
}

resource "aws_secretsmanager_secret_version" "snowflake_credentials_secret_version" {

  secret_id = aws_secretsmanager_secret.snowflake_credentials_secret.id
  secret_string = jsonencode({
    username = var.SNOWFLAKE_USERNAME
    password = var.SNOWFLAKE_PASSWORD
  })
}

resource "aws_ssm_parameter" "snowflake_connection_name" {

  name   = "/${var.APP}/${var.ENV}/snowflake/connection-name"
  type   = "String"
  value  = var.SNOWFLAKE_CONNECTION_NAME
  key_id = data.aws_kms_key.ssm_kms_key.key_id
  overwrite = true
}

resource "aws_ssm_parameter" "snowflake_host" {

  name   = "/${var.APP}/${var.ENV}/snowflake/host"
  type   = "String"
  value  = var.SNOWFLAKE_HOST
  key_id = data.aws_kms_key.ssm_kms_key.key_id
  overwrite = true
}

resource "aws_ssm_parameter" "snowflake_port" {

  name   = "/${var.APP}/${var.ENV}/snowflake/port"
  type   = "String"
  value  = var.SNOWFLAKE_PORT
  key_id = data.aws_kms_key.ssm_kms_key.key_id
  overwrite = true
}

resource "aws_ssm_parameter" "snowflake_warehouse" {

  name   = "/${var.APP}/${var.ENV}/snowflake/warehouse"
  type   = "String"
  value  = var.SNOWFLAKE_WAREHOUSE
  key_id = data.aws_kms_key.ssm_kms_key.key_id
  overwrite = true
}

resource "aws_ssm_parameter" "snowflake_database" {

  name  = "/${var.APP}/${var.ENV}/snowflake/database"
  type  = "String"
  value = var.SNOWFLAKE_DATABASE
  overwrite = true
}

resource "aws_ssm_parameter" "snowflake_schema" {

  name  = "/${var.APP}/${var.ENV}/snowflake/schema"
  type  = "String"
  value = var.SNOWFLAKE_SCHEMA
  overwrite = true
}

resource "aws_secretsmanager_secret_policy" "snowflake_secret_access_policy" {

  secret_arn = aws_secretsmanager_secret.snowflake_credentials_secret.arn
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = [
            "arn:aws:iam::${var.AWS_ACCOUNT_ID}:role/datazone_usr_role_${local.producer_project_id}_${local.smus_producer_environment_id}"
          ]
        }
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = aws_secretsmanager_secret.snowflake_credentials_secret.arn
      }
    ]
  })

  depends_on = [
    aws_secretsmanager_secret.snowflake_credentials_secret
  ]
}

resource "aws_sns_topic" "datazone_connection_lambda_dlq_topic" {

  name              = "${var.APP}-${var.ENV}-datazone-conn-lambda-dlq"
  kms_master_key_id = "alias/aws/sns"
}

data "archive_file" "datazone_connection_lambda_zip" {

  type        = "zip"
  source_file = "${path.module}/src/lambda/datazone_connection_handler.py"
  output_path = "${path.module}/src/lambda/tmp/datazone_connection_handler.zip"
}

resource "aws_lambda_function" "datazone_connection_manager" {

  function_name                  = "${var.APP}-${var.ENV}-datazone-conn-lambda"
  filename                       = data.archive_file.datazone_connection_lambda_zip.output_path
  source_code_hash               = data.archive_file.datazone_connection_lambda_zip.output_base64sha256
  handler                        = "datazone_connection_handler.lambda_handler"
  runtime                        = "python3.11"
  timeout                        = 300
  memory_size                    = 256
  role                           = aws_iam_role.datazone_connection_lambda_exec_role.arn
  reserved_concurrent_executions = 5

  # kms_key_arn = data.aws_kms_key.your_lambda_kms_key.arn 

  environment {
    variables = {
      DOMAIN_ID           = local.smus_domain_id
      PRODUCER_PROJECT_ID = local.producer_project_id
      TOOLING_ENV_ID      = local.smus_producer_environment_id
      AWS_ACCOUNT_ID      = var.AWS_ACCOUNT_ID
    }
  }

  tracing_config {
    mode = "Active"
  }

  dead_letter_config {
    target_arn = aws_sns_topic.datazone_connection_lambda_dlq_topic.arn
  }

  depends_on = [
    data.archive_file.datazone_connection_lambda_zip,
    aws_iam_role.datazone_connection_lambda_exec_role,
    aws_sns_topic.datazone_connection_lambda_dlq_topic
  ]

  # Add Checkov skips if relevant for your context, similar to the example:
  # checkov:skip=CKV_AWS_117: "Ensure that AWS Lambda function is configured inside a VPC" # Justification: "This Lambda primarily interacts with AWS DataZone APIs and STS, not requiring direct VPC resource access for its core function."
  # checkov:skip=CKV_AWS_272: "Ensure AWS Lambda function is configured to validate code-signing" # Justification: "Code artifacts are part of the project, managed via source control and internal deployment processes."
}

# In order for lambda to assume DataZone Project User's role 
# we need to update the trust policy to allow the lambda execution role
# to assume it.
resource "null_resource" "update_datazone_role_trust_policy" {

  triggers = {
    datazone_user_role_name     = "datazone_usr_role_${local.producer_project_id}_${local.smus_producer_environment_id}"
    lambda_exec_role_arn        = aws_iam_role.datazone_connection_lambda_exec_role.arn
    delay_before_update_trigger = time_sleep.pre_trust_policy_update_delay.id
  }

  provisioner "local-exec" {
    when        = create
    interpreter = ["bash", "-c"]
    command     = <<-EOT
      set -e
      DATAZONE_USER_ROLE_NAME="${self.triggers.datazone_user_role_name}"
      LAMBDA_PRINCIPAL_ARN="${self.triggers.lambda_exec_role_arn}"

      echo "DataZone User Role Name: '$DATAZONE_USER_ROLE_NAME'"
      echo "Lambda Principal ARN for policy: '$LAMBDA_PRINCIPAL_ARN'"
      echo "Checking and updating trust policy (create/update)..."

      CURRENT_POLICY_DOCUMENT_STRING=$(aws iam get-role --role-name "$DATAZONE_USER_ROLE_NAME" --query "Role.AssumeRolePolicyDocument" --output json 2>/dev/null || echo "null")

      if [ "$CURRENT_POLICY_DOCUMENT_STRING" = "null" ]; then
        echo "Error: Could not retrieve trust policy for role '$DATAZONE_USER_ROLE_NAME' or role does not exist."
        exit 1
      fi
      echo "Current Trust Policy Document (before modification) for '$DATAZONE_USER_ROLE_NAME':"
      echo "$CURRENT_POLICY_DOCUMENT_STRING" | jq .

      STATEMENT_EXISTS=$(echo "$CURRENT_POLICY_DOCUMENT_STRING" | jq --arg principal_arn "$LAMBDA_PRINCIPAL_ARN" \
        '.Statement | any(.Effect == "Allow" and .Action == "sts:AssumeRole" and .Principal.AWS == $principal_arn)')

      if [ "$STATEMENT_EXISTS" = "true" ]; then
        echo "The required trust policy statement for '$LAMBDA_PRINCIPAL_ARN' already exists in '$DATAZONE_USER_ROLE_NAME'. No changes needed."
        exit 0
      else
        echo "Required trust policy statement for '$LAMBDA_PRINCIPAL_ARN' not found in '$DATAZONE_USER_ROLE_NAME'. Adding it."
        
        NEW_STATEMENT_JSON=$(jq -n --arg principal_arn "$LAMBDA_PRINCIPAL_ARN" \
          '{Effect: "Allow", Principal: {AWS: $principal_arn}, Action: "sts:AssumeRole"}')
        
        UPDATED_POLICY_DOCUMENT_STRING=$(echo "$CURRENT_POLICY_DOCUMENT_STRING" | jq \
          --argjson stmt_obj "$NEW_STATEMENT_JSON" \
          '.Statement = (if .Statement == null then [] else .Statement end) + [$stmt_obj]')
        
        echo "Final Updated Trust Policy Document to be applied to '$DATAZONE_USER_ROLE_NAME':"
        echo "$UPDATED_POLICY_DOCUMENT_STRING" | jq .

        POLICY_FILE=$(mktemp)
        echo "Writing policy to temporary file: $POLICY_FILE"
        echo "$UPDATED_POLICY_DOCUMENT_STRING" > "$POLICY_FILE"
        
        echo "Updating IAM role trust policy using file: $POLICY_FILE"
        aws iam update-assume-role-policy --role-name "$DATAZONE_USER_ROLE_NAME" --policy-document "file://$POLICY_FILE"
        
        rm "$POLICY_FILE"
        echo "Deleted temporary policy file: $POLICY_FILE"
        
        echo "Successfully updated trust policy for '$DATAZONE_USER_ROLE_NAME' to include '$LAMBDA_PRINCIPAL_ARN'."
      fi
    EOT
  }

  provisioner "local-exec" {
    when        = destroy
    interpreter = ["bash", "-c"]
    command     = <<-EOT
      set -e
      DATAZONE_USER_ROLE_NAME="${self.triggers.datazone_user_role_name}"
      LAMBDA_PRINCIPAL_ARN="${self.triggers.lambda_exec_role_arn}"

      echo "Attempting to remove Lambda execution role ('$LAMBDA_PRINCIPAL_ARN') from trust policy of '$DATAZONE_USER_ROLE_NAME' during destroy."

      CURRENT_POLICY_DOCUMENT_STRING=$(aws iam get-role --role-name "$DATAZONE_USER_ROLE_NAME" --query "Role.AssumeRolePolicyDocument" --output json 2>/dev/null || echo "null")

      if [ "$CURRENT_POLICY_DOCUMENT_STRING" = "null" ]; then
        echo "Warning: Could not retrieve trust policy for role '$DATAZONE_USER_ROLE_NAME' (it might already be deleted or never existed). Skipping policy update."
        exit 0 
      fi
      echo "Current Trust Policy Document (before removal) for '$DATAZONE_USER_ROLE_NAME':"
      echo "$CURRENT_POLICY_DOCUMENT_STRING" | jq .

      UPDATED_POLICY_DOCUMENT_STRING=$(echo "$CURRENT_POLICY_DOCUMENT_STRING" | jq --arg principal_arn "$LAMBDA_PRINCIPAL_ARN" \
        'if .Statement then .Statement |= map(select(.Principal.AWS != $principal_arn or .Action != "sts:AssumeRole" or .Effect != "Allow")) else . end')

      echo "Trust Policy Document after attempting removal from '$DATAZONE_USER_ROLE_NAME':"
      echo "$UPDATED_POLICY_DOCUMENT_STRING" | jq .
      
      if echo "$UPDATED_POLICY_DOCUMENT_STRING" | jq -e . > /dev/null; then
        if [ "$(echo "$CURRENT_POLICY_DOCUMENT_STRING" | jq -S .)" != "$(echo "$UPDATED_POLICY_DOCUMENT_STRING" | jq -S .)" ]; then
          POLICY_FILE=$(mktemp)
          echo "Writing policy to temporary file: $POLICY_FILE"
          echo "$UPDATED_POLICY_DOCUMENT_STRING" > "$POLICY_FILE"

          echo "Updating IAM role trust policy using file: $POLICY_FILE"
          aws iam update-assume-role-policy --role-name "$DATAZONE_USER_ROLE_NAME" --policy-document "file://$POLICY_FILE"
          
          rm "$POLICY_FILE"
          echo "Deleted temporary policy file: $POLICY_FILE"
          
          echo "Successfully updated trust policy for '$DATAZONE_USER_ROLE_NAME' after attempting to remove '$LAMBDA_PRINCIPAL_ARN'."
        else
          echo "Policy for '$DATAZONE_USER_ROLE_NAME' did not change after removal attempt. No update needed."
        fi
      else
        echo "Warning: Resulting policy document for '$DATAZONE_USER_ROLE_NAME' after removal attempt was invalid or empty. Skipping update."
      fi
    EOT
  }
  depends_on = [
    aws_iam_role.datazone_connection_lambda_exec_role,
    time_sleep.pre_trust_policy_update_delay
  ]
}

resource "time_sleep" "iam_propagation_delay" {

  create_duration  = "15s"
  destroy_duration = "15s"

  triggers = {
    datazone_user_role_name = null_resource.update_datazone_role_trust_policy.triggers.datazone_user_role_name
  }
  depends_on = [null_resource.update_datazone_role_trust_policy]
}

resource "time_sleep" "pre_trust_policy_update_delay" {

  create_duration = "15s"

  triggers = {
    lambda_exec_role_arn = aws_iam_role.datazone_connection_lambda_exec_role.arn
  }

  depends_on = [
    aws_iam_role.datazone_connection_lambda_exec_role
  ]
}

resource "null_resource" "datazone_snowflake_connection_orchestrator" {

  triggers = {
    datazone_domain_id     = local.smus_domain_id
    producer_project_id    = local.producer_project_id
    tooling_environment_id = local.smus_producer_environment_id
    connection_name        = var.SNOWFLAKE_CONNECTION_NAME
    lambda_function_arn    = aws_lambda_function.datazone_connection_manager.arn
    cli_input_payload_hash = sha256(local.datazone_cli_input_json_payload)
    delay_trigger          = time_sleep.iam_propagation_delay.id
  }

  provisioner "local-exec" {
    when        = create
    interpreter = ["bash", "-c"]
    command = <<-EOT
      set -e
      echo "Invoking Lambda for Create DataZone Connection: ${self.triggers.connection_name}"
      PAYLOAD_FILE=$(mktemp)
      cat <<PAYLOAD_EOF > "$PAYLOAD_FILE"
${jsonencode({
    RequestType = "Create",
    ResourceProperties = {
      ConnectionName      = self.triggers.connection_name,
      CliInputJsonPayload = local.datazone_cli_input_json_payload
      # PhysicalResourceId is not sent for Create
    }
})}
PAYLOAD_EOF
      echo "Payload for Lambda (from $PAYLOAD_FILE):"
      cat "$PAYLOAD_FILE"
      
      # Create a temporary file for the response
      RESPONSE_FILE=$(mktemp)

      aws lambda invoke \
        --function-name "${aws_lambda_function.datazone_connection_manager.function_name}" \
        --payload fileb://"$PAYLOAD_FILE" \
        --cli-binary-format raw-in-base64-out \
        "$RESPONSE_FILE"
      
      LAMBDA_OUTPUT=$(cat "$RESPONSE_FILE")
      rm "$PAYLOAD_FILE" "$RESPONSE_FILE" # Clean up temp files

      echo "Lambda response:"
      echo "$LAMBDA_OUTPUT"
      
      if echo "$LAMBDA_OUTPUT" | jq -e '.FunctionError != null or .errorMessage != null' > /dev/null; then
        echo "Lambda invocation failed with error."
        exit 1
      fi
      
      PHYSICAL_ID=$(echo "$LAMBDA_OUTPUT" | jq -r '.PhysicalResourceId')
      if [ "$PHYSICAL_ID" = "null" ] || [ -z "$PHYSICAL_ID" ]; then
        echo "Lambda did not return a PhysicalResourceId."
        exit 1
      fi
      echo "Lambda Create invocation successful for ${self.triggers.connection_name}. PhysicalResourceId: $PHYSICAL_ID"
      # Output the PhysicalResourceId so Terraform can store it as self.id
      echo "$PHYSICAL_ID" 
    EOT
}

provisioner "local-exec" {
  when        = destroy
  interpreter = ["bash", "-c"]
  command = <<-EOT
      set -e
      echo "Invoking Lambda for Delete DataZone Connection: ${self.triggers.connection_name}"
      # For destroy, self.id should contain the PhysicalResourceId from the create operation
      PHYSICAL_RESOURCE_ID_TO_DELETE="${self.id}" 
      echo "PhysicalResourceId to delete: $PHYSICAL_RESOURCE_ID_TO_DELETE"

      if [ -z "$PHYSICAL_RESOURCE_ID_TO_DELETE" ]; then
        echo "Warning: PhysicalResourceId (self.id) is empty for destroy. Lambda might not be able to identify the specific resource."
        # To attempt delete by name as a fallback:
        # PAYLOAD_JSON_CONTENT=$(...) with only ConnectionName
      fi

      PAYLOAD_FILE=$(mktemp)
      cat <<PAYLOAD_EOF > "$PAYLOAD_FILE"
${jsonencode({
  RequestType        = "Delete",
  PhysicalResourceId = "$PHYSICAL_RESOURCE_ID_TO_DELETE",
  ResourceProperties = {
    ConnectionName = self.triggers.connection_name
    # CliInputJsonPayload is not typically needed for delete, but send props if lambda expects it
  }
})}
PAYLOAD_EOF
      echo "Payload for Lambda (from $PAYLOAD_FILE):"
      cat "$PAYLOAD_FILE"
      RESPONSE_FILE=$(mktemp)

      aws lambda invoke \
        --function-name "${self.triggers.lambda_function_arn}" \
        --payload fileb://"$PAYLOAD_FILE" \
        --cli-binary-format raw-in-base64-out \
        "$RESPONSE_FILE"

      LAMBDA_OUTPUT=$(cat "$RESPONSE_FILE")
      rm "$PAYLOAD_FILE" "$RESPONSE_FILE"

      echo "Lambda response:"
      echo "$LAMBDA_OUTPUT"
      # For destroy, we often don't want to fail the whole terraform destroy if the lambda delete fails,
      # especially if the resource might already be gone.
      if echo "$LAMBDA_OUTPUT" | jq -e '.FunctionError != null or .errorMessage != null' > /dev/null; then
        echo "Lambda delete invocation for ${self.triggers.connection_name} reported an error, but continuing destroy."
      else
        echo "Lambda Delete invocation successful or handled for ${self.triggers.connection_name}."
      fi
    EOT
}

depends_on = [
  aws_lambda_function.datazone_connection_manager,
  time_sleep.iam_propagation_delay,
]
}
