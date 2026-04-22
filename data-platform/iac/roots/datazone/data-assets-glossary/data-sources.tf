// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

# Get the Redshift workgroup created by producer project
data "aws_redshiftserverless_workgroup" "producer_workgroup" {
  workgroup_name = "redshift-serverless-workgroup-${local.producer_project_id}"
}

# Data Source for S3 Tables
resource "aws_datazone_data_source" "s3_tables" {
  domain_identifier = local.domain_id
  project_identifier = local.producer_project_id
  name               = "Financial Advisor S3 Tables"
  description        = "S3 Tables containing financial advisor data in Iceberg format"
  type               = "GLUE"
  
  configuration {
    glue_run_configuration {
      data_access_role = data.aws_iam_role.producer_role.arn
      catalog_name     = "s3tablescatalog"
      region           = var.AWS_PRIMARY_REGION
      
      relational_filter_configurations {
        database_name = "financial_advisor"
        schema_name   = "financial_advisor"
      }
    }
  }

  enable_setting = "ENABLED"
  
  publish_on_import = true
  
  recommendation_configuration {
    enable_business_name_generation = true
  }

  schedule {
    schedule = "cron(0 0 * * ? *)"  # Daily at midnight
    timezone = "UTC"
  }
}

# Data Source for Redshift Views
resource "aws_datazone_data_source" "redshift_views" {
  domain_identifier = local.domain_id
  project_identifier = local.producer_project_id
  name               = "Financial Advisor Redshift Views"
  description        = "Redshift views for financial advisor analytics"
  type               = "REDSHIFT"
  
  configuration {
    redshift_run_configuration {
      data_access_role = data.aws_iam_role.producer_role.arn
      redshift_credential_configuration {
        secret_manager_arn = aws_secretsmanager_secret.redshift_credentials.arn
      }
      redshift_storage {
        redshift_serverless_source {
          workgroup_name = data.aws_redshiftserverless_workgroup.producer_workgroup.workgroup_name
        }
      }
      
      relational_filter_configurations {
        database_name = "dev"
        schema_name   = "public"
      }
    }
  }

  enable_setting = "ENABLED"
  
  publish_on_import = true
  
  recommendation_configuration {
    enable_business_name_generation = true
  }

  schedule {
    schedule = "cron(0 1 * * ? *)"  # Daily at 1 AM
    timezone = "UTC"
  }
}

# Redshift credentials secret (placeholder - update with actual credentials)
resource "aws_secretsmanager_secret" "redshift_credentials" {
  name        = "${var.APP}-${var.ENV}-redshift-datazone-credentials"
  description = "Redshift credentials for DataZone data source"
}

resource "aws_secretsmanager_secret_version" "redshift_credentials" {
  secret_id = aws_secretsmanager_secret.redshift_credentials.id
  secret_string = jsonencode({
    username = "admin"
    password = "MLWEYsdgr540&&"  # Update this with actual password
  })
}
