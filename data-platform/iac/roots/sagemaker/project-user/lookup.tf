// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

data "aws_ssm_parameter" "owner" {

  name = "/${var.APP}/${var.ENV}/sagemaker/producer/owner"
}




   
