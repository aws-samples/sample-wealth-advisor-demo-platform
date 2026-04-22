// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

output "identity_center_arn" {
    value = local.instance_arn
}

output "identity_store_id" {
    value = local.identity_store_id
}

output "group_arns" {

    value = { for g in aws_identitystore_group.groups : g.display_name => g.id }
}

output "users" {

    value = { for u in aws_identitystore_user.users : u.user_name => u.id }
}
