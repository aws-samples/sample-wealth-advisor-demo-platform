// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

resource "aws_quicksight_dashboard" "advisor_dashboard" {
  aws_account_id      = data.aws_caller_identity.current.account_id
  dashboard_id        = "${var.APP}-${var.ENV}-advisor-dashboard"
  name                = "${var.APP}_${var.ENV}_Advisor_Dashboard"
  version_description = "1.0"

  definition {
    data_set_identifiers_declarations {
      data_set_arn = aws_quicksight_data_set.advisor_dashboard_summary.arn
      identifier   = "advisor-summary"
    }

    sheets {
      sheet_id = "advisor-overview"
      name     = "Advisor Overview"

      visuals {
        bar_chart_visual {
          visual_id = "aum-by-advisor"
          title {
            format_text {
              plain_text = "Total AUM by Advisor (Latest Month)"
            }
          }
          chart_configuration {
            field_wells {
              bar_chart_aggregated_field_wells {
                category {
                  categorical_dimension_field {
                    column {
                      column_name         = "advisor_name"
                      data_set_identifier = "advisor-summary"
                    }
                    field_id = "advisor-name"
                  }
                }
                values {
                  numerical_measure_field {
                    column {
                      column_name         = "total_aum_latest_month"
                      data_set_identifier = "advisor-summary"
                    }
                    field_id = "total-aum"
                    aggregation_function {
                      simple_numerical_aggregation = "SUM"
                    }
                  }
                }
              }
            }
            sort_configuration {
              category_sort {
                field_sort {
                  field_id  = "total-aum"
                  direction = "DESC"
                }
              }
            }
          }
        }
      }

      visuals {
        bar_chart_visual {
          visual_id = "clients-by-advisor"
          title {
            format_text {
              plain_text = "Active Clients by Advisor"
            }
          }
          chart_configuration {
            field_wells {
              bar_chart_aggregated_field_wells {
                category {
                  categorical_dimension_field {
                    column {
                      column_name         = "advisor_name"
                      data_set_identifier = "advisor-summary"
                    }
                    field_id = "advisor-name-clients"
                  }
                }
                values {
                  numerical_measure_field {
                    column {
                      column_name         = "active_clients_latest_month"
                      data_set_identifier = "advisor-summary"
                    }
                    field_id = "active-clients"
                    aggregation_function {
                      simple_numerical_aggregation = "SUM"
                    }
                  }
                }
              }
            }
            sort_configuration {
              category_sort {
                field_sort {
                  field_id  = "active-clients"
                  direction = "DESC"
                }
              }
            }
          }
        }
      }

      visuals {
        bar_chart_visual {
          visual_id = "fees-by-advisor"
          title {
            format_text {
              plain_text = "Total Fees by Advisor (Latest Month)"
            }
          }
          chart_configuration {
            field_wells {
              bar_chart_aggregated_field_wells {
                category {
                  categorical_dimension_field {
                    column {
                      column_name         = "advisor_name"
                      data_set_identifier = "advisor-summary"
                    }
                    field_id = "advisor-name-fees"
                  }
                }
                values {
                  numerical_measure_field {
                    column {
                      column_name         = "total_fees_latest_month"
                      data_set_identifier = "advisor-summary"
                    }
                    field_id = "total-fees"
                    aggregation_function {
                      simple_numerical_aggregation = "SUM"
                    }
                  }
                }
              }
            }
            sort_configuration {
              category_sort {
                field_sort {
                  field_id  = "total-fees"
                  direction = "DESC"
                }
              }
            }
          }
        }
      }

      visuals {
        table_visual {
          visual_id = "advisor-details-table"
          title {
            format_text {
              plain_text = "Advisor Performance Summary"
            }
          }
          chart_configuration {
            field_wells {
              table_aggregated_field_wells {
                group_by {
                  categorical_dimension_field {
                    column {
                      column_name         = "advisor_name"
                      data_set_identifier = "advisor-summary"
                    }
                    field_id = "advisor-name-table"
                  }
                }
                values {
                  numerical_measure_field {
                    column {
                      column_name         = "total_aum_latest_month"
                      data_set_identifier = "advisor-summary"
                    }
                    field_id = "aum-table"
                    aggregation_function {
                      simple_numerical_aggregation = "SUM"
                    }
                  }
                }
                values {
                  numerical_measure_field {
                    column {
                      column_name         = "aum_change_pct"
                      data_set_identifier = "advisor-summary"
                    }
                    field_id = "aum-change-pct-table"
                    aggregation_function {
                      simple_numerical_aggregation = "AVERAGE"
                    }
                  }
                }
                values {
                  numerical_measure_field {
                    column {
                      column_name         = "avg_portfolio_return_pct"
                      data_set_identifier = "advisor-summary"
                    }
                    field_id = "return-pct-table"
                    aggregation_function {
                      simple_numerical_aggregation = "AVERAGE"
                    }
                  }
                }
                values {
                  numerical_measure_field {
                    column {
                      column_name         = "active_clients_latest_month"
                      data_set_identifier = "advisor-summary"
                    }
                    field_id = "clients-table"
                    aggregation_function {
                      simple_numerical_aggregation = "SUM"
                    }
                  }
                }
                values {
                  numerical_measure_field {
                    column {
                      column_name         = "total_fees_latest_month"
                      data_set_identifier = "advisor-summary"
                    }
                    field_id = "fees-table"
                    aggregation_function {
                      simple_numerical_aggregation = "SUM"
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }

  permissions {
    actions = [
      "quicksight:DescribeDashboard",
      "quicksight:ListDashboardVersions",
      "quicksight:UpdateDashboardPermissions",
      "quicksight:QueryDashboard",
      "quicksight:UpdateDashboard",
      "quicksight:DeleteDashboard",
      "quicksight:DescribeDashboardPermissions",
      "quicksight:UpdateDashboardPublishedVersion"
    ]
    principal = data.external.quicksight_user.result.arn
  }

  dashboard_publish_options {
    ad_hoc_filtering_option {
      availability_status = "ENABLED"
    }
    export_to_csv_option {
      availability_status = "ENABLED"
    }
    sheet_controls_option {
      visibility_state = "EXPANDED"
    }
  }
}
