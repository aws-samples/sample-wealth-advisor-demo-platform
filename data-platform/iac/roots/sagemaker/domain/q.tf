// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

resource "aws_ssm_parameter" "q_enabled" {

  name        = "/amazon/datazone/q/${local.domain_id}/q-enabled"
  type        = "String"
  value       = "true"
  description = "Whether to enable Amazon Q for this domain"
  # key_id      = data.aws_kms_key.ssm_kms_key.key_id
  overwrite = true
}

# Set auth-mode as IAM
resource "aws_ssm_parameter" "q_auth_mode" {

  name        = "/amazon/datazone/q/${local.domain_id}/auth-mode"
  type        = "String"
  value       = "IAM"
  description = "Authentication mode for Amazon Q"
  # key_id      = data.aws_kms_key.ssm_kms_key.key_id
  overwrite = true
}
