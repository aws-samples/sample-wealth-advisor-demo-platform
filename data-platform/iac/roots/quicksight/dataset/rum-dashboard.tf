// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

resource "aws_quicksight_dashboard" "rum_dashboard" {
  aws_account_id      = data.aws_caller_identity.current.account_id
  dashboard_id        = "${var.APP}-${var.ENV}-rum-dashboard"
  name                = "${var.APP}_${var.ENV}_RUM_Dashboard"
  version_description = "1.0"

  definition {
    data_set_identifiers_declarations {
      data_set_arn = aws_quicksight_data_set.rum_page_views.arn
      identifier   = "page-views"
    }
    data_set_identifiers_declarations {
      data_set_arn = aws_quicksight_data_set.rum_errors.arn
      identifier   = "errors"
    }
    data_set_identifiers_declarations {
      data_set_arn = aws_quicksight_data_set.rum_performance.arn
      identifier   = "performance"
    }

    sheets {
      sheet_id = "rum-overview"
      name     = "RUM Overview"

      visuals {
        line_chart_visual {
          visual_id = "page-views-over-time"
          title {
            format_text {
              plain_text = "Page Views Over Time"
            }
          }
          chart_configuration {
            field_wells {
              line_chart_aggregated_field_wells {
                category {
                  date_dimension_field {
                    column {
                      column_name         = "view_timestamp"
                      data_set_identifier = "page-views"
                    }
                    field_id = "view-timestamp"
                  }
                }
                values {
                  numerical_measure_field {
                    column {
                      column_name         = "load_time_ms"
                      data_set_identifier = "page-views"
                    }
                    field_id = "view-count"
                    aggregation_function {
                      simple_numerical_aggregation = "COUNT"
                    }
                  }
                }
              }
            }
          }
        }
      }

      visuals {
        bar_chart_visual {
          visual_id = "top-pages"
          title {
            format_text {
              plain_text = "Top Pages by Views"
            }
          }
          chart_configuration {
            field_wells {
              bar_chart_aggregated_field_wells {
                category {
                  categorical_dimension_field {
                    column {
                      column_name         = "page_url"
                      data_set_identifier = "page-views"
                    }
                    field_id = "page-url"
                  }
                }
                values {
                  numerical_measure_field {
                    column {
                      column_name         = "load_time_ms"
                      data_set_identifier = "page-views"
                    }
                    field_id = "page-view-count"
                    aggregation_function {
                      simple_numerical_aggregation = "COUNT"
                    }
                  }
                }
              }
            }
            sort_configuration {
              category_sort {
                field_sort {
                  field_id  = "page-view-count"
                  direction = "DESC"
                }
              }
            }
          }
        }
      }

      visuals {
        bar_chart_visual {
          visual_id = "avg-load-time"
          title {
            format_text {
              plain_text = "Average Load Time by Page (ms)"
            }
          }
          chart_configuration {
            field_wells {
              bar_chart_aggregated_field_wells {
                category {
                  categorical_dimension_field {
                    column {
                      column_name         = "page_url"
                      data_set_identifier = "page-views"
                    }
                    field_id = "page-url-load"
                  }
                }
                values {
                  numerical_measure_field {
                    column {
                      column_name         = "load_time_ms"
                      data_set_identifier = "page-views"
                    }
                    field_id = "avg-load-time"
                    aggregation_function {
                      simple_numerical_aggregation = "AVERAGE"
                    }
                  }
                }
              }
            }
            sort_configuration {
              category_sort {
                field_sort {
                  field_id  = "avg-load-time"
                  direction = "DESC"
                }
              }
            }
          }
        }
      }

      visuals {
        pie_chart_visual {
          visual_id = "errors-by-type"
          title {
            format_text {
              plain_text = "Errors by Type"
            }
          }
          chart_configuration {
            field_wells {
              pie_chart_aggregated_field_wells {
                category {
                  categorical_dimension_field {
                    column {
                      column_name         = "error_type"
                      data_set_identifier = "errors"
                    }
                    field_id = "error-type"
                  }
                }
                values {
                  numerical_measure_field {
                    column {
                      column_name         = "http_status"
                      data_set_identifier = "errors"
                    }
                    field_id = "error-count"
                    aggregation_function {
                      simple_numerical_aggregation = "COUNT"
                    }
                  }
                }
              }
            }
          }
        }
      }

      visuals {
        pie_chart_visual {
          visual_id = "views-by-device"
          title {
            format_text {
              plain_text = "Page Views by Device Type"
            }
          }
          chart_configuration {
            field_wells {
              pie_chart_aggregated_field_wells {
                category {
                  categorical_dimension_field {
                    column {
                      column_name         = "device_type"
                      data_set_identifier = "page-views"
                    }
                    field_id = "device-type"
                  }
                }
                values {
                  numerical_measure_field {
                    column {
                      column_name         = "load_time_ms"
                      data_set_identifier = "page-views"
                    }
                    field_id = "device-view-count"
                    aggregation_function {
                      simple_numerical_aggregation = "COUNT"
                    }
                  }
                }
              }
            }
          }
        }
      }

      visuals {
        table_visual {
          visual_id = "perf-by-page"
          title {
            format_text {
              plain_text = "Core Web Vitals by Page"
            }
          }
          chart_configuration {
            field_wells {
              table_aggregated_field_wells {
                group_by {
                  categorical_dimension_field {
                    column {
                      column_name         = "page_url"
                      data_set_identifier = "performance"
                    }
                    field_id = "perf-page-url"
                  }
                }
                values {
                  numerical_measure_field {
                    column {
                      column_name         = "ttfb_ms"
                      data_set_identifier = "performance"
                    }
                    field_id = "avg-ttfb"
                    aggregation_function {
                      simple_numerical_aggregation = "AVERAGE"
                    }
                  }
                }
                values {
                  numerical_measure_field {
                    column {
                      column_name         = "fcp_ms"
                      data_set_identifier = "performance"
                    }
                    field_id = "avg-fcp"
                    aggregation_function {
                      simple_numerical_aggregation = "AVERAGE"
                    }
                  }
                }
                values {
                  numerical_measure_field {
                    column {
                      column_name         = "lcp_ms"
                      data_set_identifier = "performance"
                    }
                    field_id = "avg-lcp"
                    aggregation_function {
                      simple_numerical_aggregation = "AVERAGE"
                    }
                  }
                }
                values {
                  numerical_measure_field {
                    column {
                      column_name         = "cls_score"
                      data_set_identifier = "performance"
                    }
                    field_id = "avg-cls"
                    aggregation_function {
                      simple_numerical_aggregation = "AVERAGE"
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
