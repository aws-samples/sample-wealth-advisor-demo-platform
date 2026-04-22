// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

# Lake Formation permissions are managed separately through AWS console or CLI
# The catalog_resource permissions cannot be granted via Terraform for S3 Tables catalogs
# as they require special handling for federated catalogs
