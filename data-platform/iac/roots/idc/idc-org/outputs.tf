// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

output "identity_center_arn" {

    value = data.aws_ssoadmin_instances.identity_center.arns
}

output "identity_store_id" {

    value = data.aws_ssoadmin_instances.identity_center.identity_store_ids
}

output "group_arns" {

    value = { for g in aws_identitystore_group.groups : g.display_name => g.id }
}

output "permission_set_arns" {

    value = { for name, ps in aws_ssoadmin_permission_set.permissions : name => ps.arn }
}

output "users" {

    value = { for u in aws_identitystore_user.users : u.user_name => u.id }
}
