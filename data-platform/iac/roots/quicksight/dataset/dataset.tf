// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

data "external" "quicksight_user" {
  program = ["bash", "-c", "aws quicksight list-users --aws-account-id ${data.aws_caller_identity.current.account_id} --namespace default --region ${var.AWS_PRIMARY_REGION} --query 'UserList[0].Arn' --output text | jq -R '{arn: .}'"]
}

resource "aws_quicksight_vpc_connection" "redshift_vpc" {
  aws_account_id     = data.aws_caller_identity.current.account_id
  vpc_connection_id  = "financial-advisor-redshift-vpc"
  name               = "Financial Advisor Redshift VPC"
  role_arn           = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${var.QUICKSIGHT_ROLE}"
  subnet_ids         = local.subnet_ids
  security_group_ids = [local.security_group_id]
}

resource "aws_quicksight_data_source" "redshift" {
  aws_account_id = data.aws_caller_identity.current.account_id
  data_source_id = "financial-advisor-redshift"
  name           = "Financial Advisor Redshift"
  type           = "REDSHIFT"

  parameters {
    redshift {
      database = "dev"
      host     = local.redshift_endpoint
      port     = 5439
    }
  }

  credentials {
    credential_pair {
      username = local.redshift_creds.username
      password = local.redshift_creds.password
    }
  }

  vpc_connection_properties {
    vpc_connection_arn = aws_quicksight_vpc_connection.redshift_vpc.arn
  }

  permission {
    actions = [
      "quicksight:DescribeDataSource",
      "quicksight:DescribeDataSourcePermissions",
      "quicksight:PassDataSource",
      "quicksight:UpdateDataSource",
      "quicksight:DeleteDataSource",
      "quicksight:UpdateDataSourcePermissions"
    ]
    principal = data.external.quicksight_user.result.arn
  }
}

resource "aws_quicksight_data_set" "advisor_dashboard_summary" {
  aws_account_id = data.aws_caller_identity.current.account_id
  data_set_id    = "financial-advisor-advisor-dashboard-summary"
  name           = "Financial Advisor - Advisor Dashboard Summary"
  import_mode    = "DIRECT_QUERY"

  physical_table_map {
    physical_table_map_id = "advisor-dashboard-summary"
    relational_table {
      data_source_arn = aws_quicksight_data_source.redshift.arn
      schema          = "public"
      name            = "qs_advisor_dashboard_summary"
      input_columns {
        name = "advisor_id"
        type = "STRING"
      }
      input_columns {
        name = "advisor_name"
        type = "STRING"
      }
      input_columns {
        name = "advisor_title"
        type = "STRING"
      }
      input_columns {
        name = "latest_month"
        type = "DATETIME"
      }
      input_columns {
        name = "previous_month"
        type = "DATETIME"
      }
      input_columns {
        name = "total_aum_latest_month"
        type = "DECIMAL"
      }
      input_columns {
        name = "total_aum_previous_month"
        type = "DECIMAL"
      }
      input_columns {
        name = "aum_change"
        type = "DECIMAL"
      }
      input_columns {
        name = "aum_change_pct"
        type = "DECIMAL"
      }
      input_columns {
        name = "avg_portfolio_return_pct"
        type = "DECIMAL"
      }
      input_columns {
        name = "avg_portfolio_return_value"
        type = "DECIMAL"
      }
      input_columns {
        name = "active_clients_latest_month"
        type = "INTEGER"
      }
      input_columns {
        name = "active_clients_previous_month"
        type = "INTEGER"
      }
      input_columns {
        name = "active_clients_change"
        type = "INTEGER"
      }
      input_columns {
        name = "total_fees_latest_month"
        type = "DECIMAL"
      }
      input_columns {
        name = "total_fees_previous_month"
        type = "DECIMAL"
      }
      input_columns {
        name = "fees_change"
        type = "DECIMAL"
      }
    }
  }

  permissions {
    actions = [
      "quicksight:DescribeDataSet",
      "quicksight:DescribeDataSetPermissions",
      "quicksight:PassDataSet",
      "quicksight:UpdateDataSet",
      "quicksight:DeleteDataSet",
      "quicksight:CreateIngestion",
      "quicksight:ListIngestions",
      "quicksight:DescribeIngestion",
      "quicksight:CancelIngestion",
      "quicksight:UpdateDataSetPermissions"
    ]
    principal = data.external.quicksight_user.result.arn
  }
}

resource "aws_quicksight_data_set" "rum_page_views" {
  aws_account_id = data.aws_caller_identity.current.account_id
  data_set_id    = "rum-page-views"
  name           = "RUM Page Views"
  import_mode    = "DIRECT_QUERY"

  physical_table_map {
    physical_table_map_id = "rum-page-views"
    relational_table {
      data_source_arn = aws_quicksight_data_source.redshift.arn
      schema          = "public"
      name            = "rum_page_views"
      input_columns {
        name = "view_id"
        type = "STRING"
      }
      input_columns {
        name = "session_id"
        type = "STRING"
      }
      input_columns {
        name = "page_url"
        type = "STRING"
      }
      input_columns {
        name = "page_title"
        type = "STRING"
      }
      input_columns {
        name = "load_time_ms"
        type = "INTEGER"
      }
      input_columns {
        name = "device_type"
        type = "STRING"
      }
      input_columns {
        name = "browser"
        type = "STRING"
      }
      input_columns {
        name = "country"
        type = "STRING"
      }
      input_columns {
        name = "city"
        type = "STRING"
      }
      input_columns {
        name = "view_timestamp"
        type = "DATETIME"
      }
    }
  }

  permissions {
    actions = [
      "quicksight:DescribeDataSet",
      "quicksight:DescribeDataSetPermissions",
      "quicksight:PassDataSet",
      "quicksight:UpdateDataSet",
      "quicksight:DeleteDataSet",
      "quicksight:CreateIngestion",
      "quicksight:ListIngestions",
      "quicksight:DescribeIngestion",
      "quicksight:CancelIngestion",
      "quicksight:UpdateDataSetPermissions"
    ]
    principal = data.external.quicksight_user.result.arn
  }
}

resource "aws_quicksight_data_set" "rum_errors" {
  aws_account_id = data.aws_caller_identity.current.account_id
  data_set_id    = "rum-errors"
  name           = "RUM Errors"
  import_mode    = "DIRECT_QUERY"

  physical_table_map {
    physical_table_map_id = "rum-errors"
    relational_table {
      data_source_arn = aws_quicksight_data_source.redshift.arn
      schema          = "public"
      name            = "rum_errors"
      input_columns {
        name = "error_id"
        type = "STRING"
      }
      input_columns {
        name = "session_id"
        type = "STRING"
      }
      input_columns {
        name = "error_type"
        type = "STRING"
      }
      input_columns {
        name = "error_message"
        type = "STRING"
      }
      input_columns {
        name = "page_url"
        type = "STRING"
      }
      input_columns {
        name = "http_status"
        type = "INTEGER"
      }
      input_columns {
        name = "error_timestamp"
        type = "DATETIME"
      }
    }
  }

  permissions {
    actions = [
      "quicksight:DescribeDataSet",
      "quicksight:DescribeDataSetPermissions",
      "quicksight:PassDataSet",
      "quicksight:UpdateDataSet",
      "quicksight:DeleteDataSet",
      "quicksight:CreateIngestion",
      "quicksight:ListIngestions",
      "quicksight:DescribeIngestion",
      "quicksight:CancelIngestion",
      "quicksight:UpdateDataSetPermissions"
    ]
    principal = data.external.quicksight_user.result.arn
  }
}

resource "aws_quicksight_data_set" "rum_performance" {
  aws_account_id = data.aws_caller_identity.current.account_id
  data_set_id    = "rum-performance"
  name           = "RUM Performance"
  import_mode    = "DIRECT_QUERY"

  physical_table_map {
    physical_table_map_id = "rum-performance"
    relational_table {
      data_source_arn = aws_quicksight_data_source.redshift.arn
      schema          = "public"
      name            = "rum_performance"
      input_columns {
        name = "perf_id"
        type = "STRING"
      }
      input_columns {
        name = "session_id"
        type = "STRING"
      }
      input_columns {
        name = "page_url"
        type = "STRING"
      }
      input_columns {
        name = "ttfb_ms"
        type = "INTEGER"
      }
      input_columns {
        name = "fcp_ms"
        type = "INTEGER"
      }
      input_columns {
        name = "lcp_ms"
        type = "INTEGER"
      }
      input_columns {
        name = "cls_score"
        type = "DECIMAL"
      }
      input_columns {
        name = "fid_ms"
        type = "INTEGER"
      }
      input_columns {
        name = "dom_load_ms"
        type = "INTEGER"
      }
      input_columns {
        name = "perf_timestamp"
        type = "DATETIME"
      }
    }
  }

  permissions {
    actions = [
      "quicksight:DescribeDataSet",
      "quicksight:DescribeDataSetPermissions",
      "quicksight:PassDataSet",
      "quicksight:UpdateDataSet",
      "quicksight:DeleteDataSet",
      "quicksight:CreateIngestion",
      "quicksight:ListIngestions",
      "quicksight:DescribeIngestion",
      "quicksight:CancelIngestion",
      "quicksight:UpdateDataSetPermissions"
    ]
    principal = data.external.quicksight_user.result.arn
  }
}
