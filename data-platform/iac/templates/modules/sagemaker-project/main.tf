// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

terraform {
  required_version = ">= 1.8.0"
}

data "aws_ssoadmin_instances" "identity_center" {}
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

data "aws_kms_key" "ssm_kms_key" {

  key_id   = "alias/${var.SSM_KMS_KEY_ALIAS}"
}

locals {
  account_id       = data.aws_caller_identity.current.account_id
  region           = data.aws_region.current.name
  lambda_file_path = "src/lambda"
  lambda_file      = "src/lambda/datazone-project.py"
  LambdaRuntime    = "python3.10"
  lambda_zip_file  = "datazone-project.zip"
  stack_name = replace(var.PROJECT_NAME, " ", "-")
  json_data = jsondecode(data.aws_ssm_parameter.user_mappings.value)


  # Extract only Domain Owner ID
  project_owner_emails = flatten([
    for domain, groups in local.json_data : groups["Project Owner"]
  ])  # Taking all the Project Owner emails
}

data "aws_identitystore_user" "project_owners" {
  for_each = toset(nonsensitive(local.project_owner_emails))

  identity_store_id = data.aws_ssoadmin_instances.identity_center.identity_store_ids[0]
  alternate_identifier {
    unique_attribute {
      attribute_path  = "UserName"
      attribute_value = each.key
    }
  }
}

locals{
  project_owner_ids = [
    for email in nonsensitive(local.project_owner_emails) :
    data.aws_identitystore_user.project_owners[email].user_id
  ]

  parameters = {
      S3Bucket            = var.S3BUCKET
      DomainId            = data.aws_ssm_parameter.smus_domain_id.value
      DomainUnitId        = data.aws_ssm_parameter.smus_domain_id.value
      ProjectName         = var.PROJECT_NAME
      ProjectDescription  = var.PROJECT_DESCRIPTION
      ProjectOwner        = join(",",local.project_owner_ids)
      UserType            = var.USER_TYPE
      GlueDB              = var.GLUE_DB
      ProjectProfileId    = data.aws_ssm_parameter.smus_profile_4.value
      LambdaRuntime       = local.LambdaRuntime 
      LambdaLayerName     = data.aws_ssm_parameter.smus_lambda_layer_arn.value
      LambdaExecutionRole =  data.aws_ssm_parameter.smus_lambda_service_role_name.value
  }
}



resource "null_resource" "lambda_file" {

  triggers = {
    requirements = filesha1("${path.module}/${local.lambda_file}")
  }
  # the command to install python and dependencies to the machine and zips
  provisioner "local-exec" {
    command = <<EOT
      pwd
      cd ${path.module}/${local.lambda_file_path}
      rm -Rf tmp
      mkdir tmp
      zip tmp/${local.lambda_zip_file} datazone*.*
    EOT
  }
}

# Upload the lambda function to S3
resource "aws_s3_object" "lambdafunction" {
  
  bucket = var.S3BUCKET
  key    = local.lambda_zip_file
  source = "${path.module}/${local.lambda_file_path}/tmp/${local.lambda_zip_file}"

  depends_on = [ null_resource.lambda_file ]
}

# Create the datazone project using cfn
resource "aws_cloudformation_stack" "project" {

  parameters = local.parameters

  name         = replace("${data.aws_ssm_parameter.smus_domain_id.value}-${local.stack_name}", "_", "-")
  capabilities = var.capabilities

  template_body = file("${path.module}/src/project.yaml")

  depends_on = [ aws_s3_object.lambdafunction ]

  #checkov:skip=CKV_AWS_124: "Ensure that CloudFormation stacks are sending event notifications to an SNS topic": "Skipping this for simplicity"
}

# Save the project in SSM Parameter Store
resource "aws_ssm_parameter" "sagemaker_project_id" {

  name  = "/${var.APP}/${var.ENV}/project-${local.stack_name}"
  type  = "SecureString"
  value = aws_cloudformation_stack.project.outputs["ProjectId"]
  key_id = data.aws_kms_key.ssm_kms_key.id

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage       = "SSagemaker Domain project"
  }

  depends_on = [ aws_cloudformation_stack.project ]
  overwrite = true
}


# Save the project owner in SSM Parameter Store
resource "aws_ssm_parameter" "sagemaker_project_owner_name" {

  name  = "/${var.APP}/${var.ENV}/project-${local.stack_name}-owner"
  type  = "SecureString"
  value = join(",",local.project_owner_ids)
  key_id = data.aws_kms_key.ssm_kms_key.id

  tags = {
    Application = var.APP
    Environment = var.ENV
    Usage       = "Sagemaker Domain project"
  }

  depends_on = [ aws_cloudformation_stack.project ]
  overwrite = true
}





