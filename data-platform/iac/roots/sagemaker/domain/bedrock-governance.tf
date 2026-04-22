// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

locals {
  genai_profile_id = local.profile_ids[0]
}

resource "awscc_datazone_project" "model_governance_project" {
  domain_identifier  = local.domain_id
  name               = "GenerativeAIModelGovernanceProject"
  description        = "Model governance project for managing Bedrock models"
  project_profile_id = local.genai_profile_id

  depends_on = [aws_datazone_domain.smus_domain]
}

resource "awscc_datazone_project_membership" "governance_members" {
  for_each = toset(nonsensitive(local.domain_owner_emails))

  domain_identifier  = local.domain_id
  project_identifier = awscc_datazone_project.model_governance_project.project_id
  designation        = "PROJECT_OWNER"

  member = {
    user_identifier = data.aws_identitystore_user.domain_owners[each.key].user_id
  }

  depends_on = [
    awscc_datazone_project.model_governance_project,
    awscc_datazone_user_profile.users
  ]
}
