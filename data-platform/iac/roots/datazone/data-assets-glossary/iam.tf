// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

data "aws_iam_role" "producer_role" {
  name = "datazone_usr_role_${replace(local.producer_project_id, "-", "_")}"
}

data "aws_iam_role" "consumer_role" {
  name = "datazone_usr_role_${replace(local.consumer_project_id, "-", "_")}"
}
