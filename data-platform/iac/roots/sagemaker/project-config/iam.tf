// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

resource "aws_iam_policy" "project_policy_s3" {

  name = "${var.APP}-${var.ENV}-project-role-policy-s3"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid = "S3AccountLevelActions"
        Action = [
          "s3:ListAllMyBuckets",
          "s3:ListJobs",
          "s3:CreateJob",
          "s3:GetAccountPublicAccessBlock",
          "s3:ListStorageLensConfigurations",
          "s3:ListStorageLensGroups",
          "s3:ListAccessGrantsInstances",
          "s3:ListMultiRegionAccessPoints",
          "s3:DescribeMultiRegionAccessPointOperation",
          "s3:ListCallerAccessGrants",
          "s3:GetStorageLensDashboard",
          "s3:GetStorageLensConfiguration",
          "s3:GetStorageLensConfigurationTagging",
          "s3:GetStorageLensGroup",
          "s3:GetAccessGrantsInstance",
          "s3:GetAccessGrantsInstanceForPrefix",
          "s3:GetAccessGrantsInstanceResourcePolicy",
          "s3:ListAccessGrantsLocations",
          "s3:ListAccessGrants",
          "s3:GetDataAccess",
          "s3:GenerateRandom"
        ]
        Effect   = "Allow"
        Resource = "*"
      },
      {
        Sid = "S3ResourceLevelActions"
        Action = [
          "s3:ListAccessPointsForObjectLambda",
          "s3:DeleteAccessGrant",
          "s3:DeleteAccessPoint",
          "s3:DeleteAccessPointForObjectLambda",
          "s3:PutLifecycleConfiguration",
          "s3:DeleteObject",
          "s3:GetBucketWebsite",
          "s3:DeleteAccessGrantsInstanceResourcePolicy",
          "s3:GetObjectAttributes",
          "s3:GetObjectLegalHold",
          "s3:GetBucketNotification",
          "s3:GetReplicationConfiguration",
          "s3:PutObject",
          "s3:PutBucketNotification",
          "s3:CreateAccessGrant",
          "s3:PutBucketObjectLockConfiguration",
          "s3:DeleteBucketMetadataTableConfiguration",
          "s3:GetLifecycleConfiguration",
          "s3:GetBucketTagging",
          "s3:GetInventoryConfiguration",
          "s3:GetAccessPointPolicyForObjectLambda",
          "s3:ListBucket",
          "s3:AbortMultipartUpload",
          "s3:AssociateAccessGrantsIdentityCenter",
          "s3:UpdateJobPriority",
          "s3:PutBucketVersioning",
          "s3:ListBucketMultipartUploads",
          "s3:PutIntelligentTieringConfiguration",
          "s3:PutMetricsConfiguration",
          "s3:CreateStorageLensGroup",
          "s3:GetBucketVersioning",
          "s3:GetAccessPointConfigurationForObjectLambda",
          "s3:CreateAccessGrantsInstance",
          "s3:PutInventoryConfiguration",
          "s3:DeleteStorageLensConfiguration",
          "s3:PutBucketWebsite",
          "s3:PutBucketRequestPayment",
          "s3:PutObjectRetention",
          "s3:CreateAccessPointForObjectLambda",
          "s3:GetBucketCORS",
          "s3:PutAccessGrantsInstanceResourcePolicy",
          "s3:GetObjectVersion",
          "s3:PutAnalyticsConfiguration",
          "s3:PutAccessPointConfigurationForObjectLambda",
          "s3:GetObjectVersionTagging",
          "s3:PutStorageLensConfiguration",
          "s3:CreateBucket",
          "s3:CreateBucketMetadataTableConfiguration",
          "s3:GetObjectAcl",
          "s3:GetBucketObjectLockConfiguration",
          "s3:GetIntelligentTieringConfiguration",
          "s3:GetObjectVersionAcl",
          "s3:GetBucketPolicyStatus",
          "s3:GetAccessGrantsLocation",
          "s3:GetObjectRetention",
          "s3:GetJobTagging",
          "s3:PutObjectLegalHold",
          "s3:PutBucketCORS",
          "s3:ListMultipartUploadParts",
          "s3:GetObject",
          "s3:GetBucketMetadataTableConfiguration",
          "s3:DescribeJob",
          "s3:PutBucketLogging",
          "s3:GetAnalyticsConfiguration",
          "s3:GetObjectVersionForReplication",
          "s3:GetAccessPointForObjectLambda",
          "s3:CreateAccessPoint",
          "s3:GetAccessPoint",
          "s3:PutAccelerateConfiguration",
          "s3:DeleteObjectVersion",
          "s3:GetBucketLogging",
          "s3:ListBucketVersions",
          "s3:GetAccessGrant",
          "s3:RestoreObject",
          "s3:GetAccelerateConfiguration",
          "s3:GetObjectVersionAttributes",
          "s3:GetBucketPolicy",
          "s3:ListTagsForResource",
          "s3:PutEncryptionConfiguration",
          "s3:GetEncryptionConfiguration",
          "s3:GetObjectVersionTorrent",
          "s3:GetBucketRequestPayment",
          "s3:GetAccessPointPolicyStatus",
          "s3:DeleteStorageLensGroup",
          "s3:GetObjectTagging",
          "s3:GetBucketOwnershipControls",
          "s3:GetMetricsConfiguration",
          "s3:GetBucketPublicAccessBlock",
          "s3:GetAccessPointPolicyStatusForObjectLambda",
          "s3:ListAccessPoints",
          "s3:UpdateStorageLensGroup",
          "s3:UpdateJobStatus",
          "s3:GetBucketAcl",
          "s3:GetObjectTorrent",
          "s3:UpdateAccessGrantsLocation",
          "s3:GetBucketLocation",
          "s3:GetAccessPointPolicy"
        ]
        Effect   = "Allow"
        Resource = [
          "arn:aws:s3:::${local.account_id}-${var.APP}-${var.ENV}-*",
          "arn:aws:s3:::${local.account_id}-${var.APP}-${var.ENV}-*/*",
          "arn:aws:s3:::${var.APP}-${var.ENV}-*",
          "arn:aws:s3:::${var.APP}-${var.ENV}-*/*",
          "arn:aws:s3:::amazon-sagemaker-${local.account_id}-*",
          "arn:aws:s3:::amazon-sagemaker-${local.account_id}-*/*"
        ]
      }
    ]
  })

  #checkov:skip=CKV_AWS_288: "Ensure IAM policies does not allow data exfiltration": "Skipping this for simplicity"
  #checkov:skip=CKV_AWS_289: "Ensure IAM policies does not allow permissions management / resource exposure without constraints": "Skipping this for simplicity"
  #checkov:skip=CKV_AWS_290: "Ensure IAM policies does not allow write access without constraints": "Skipping this for simplicity"
  #checkov:skip=CKV_AWS_355: "Ensure no IAM policies documents allow "*" as a statement's resource for restrictable actions": "Skipping this for simplicity"
}

resource "aws_iam_policy" "project_policy_s3_tables" {

  name = "${var.APP}-${var.ENV}-project-role-policy-s3-tables"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3tables:CreateTableBucket",
          "s3tables:GetTablePolicy",
          "s3tables:GetTable",
          "s3tables:DeleteTable",
          "s3tables:CreateTable",
          "s3tables:GetNamespace",
          "s3tables:DeleteTableBucket",
          "s3tables:PutTableData",
          "s3tables:CreateNamespace",
          "s3tables:DeleteNamespace",
          "s3tables:GetTableBucketMaintenanceConfiguration",
          "s3tables:GetTableMaintenanceJobStatus",
          "s3tables:ListTables",
          "s3tables:GetTableMetadataLocation",
          "s3tables:UpdateTableMetadataLocation",
          "s3tables:RenameTable",
          "s3tables:GetTableData",
          "s3tables:ListNamespaces",
          "s3tables:PutTableMaintenanceConfiguration",
          "s3tables:ListTableBuckets",
          "s3tables:GetTableBucket",
          "s3tables:PutTableBucketMaintenanceConfiguration",
          "s3tables:GetTableMaintenanceConfiguration",
          "s3tables:GetTableBucketPolicy"
        ]
        Effect   = "Allow"
        Resource = "*"
      }
    ]
  })

  #checkov:skip=CKV_AWS_288: "Ensure IAM policies does not allow data exfiltration": "Skipping this for simplicity"
  #checkov:skip=CKV_AWS_289: "Ensure IAM policies does not allow permissions management / resource exposure without constraints": "Skipping this for simplicity"
  #checkov:skip=CKV_AWS_290: "Ensure IAM policies does not allow write access without constraints": "Skipping this for simplicity"
  #checkov:skip=CKV_AWS_355: "Ensure no IAM policies documents allow "*" as a statement's resource for restrictable actions": "Skipping this for simplicity"
}

resource "aws_iam_policy" "project_policy_kms" {

  name = "${var.APP}-${var.ENV}-project-role-policy-kms"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid = "KMSAccountLevelActions"
        Action = [
          "kms:GenerateRandom",
          "kms:DescribeCustomKeyStores",
          "kms:ListKeys",
          "kms:ListAliases"
        ]
        Effect   = "Allow"
        Resource = "*"
      },
      {
        Sid = "KMSKeyLevelActions"
        Action = [
          "kms:GetPublicKey",
          "kms:Decrypt",
          "kms:ListKeyPolicies",
          "kms:ListKeyRotations",
          "kms:ListRetirableGrants",
          "kms:GetKeyPolicy",
          "kms:ListResourceTags",
          "kms:GenerateDataKey",
          "kms:GenerateDataKeyPairWithoutPlaintext",
          "kms:GenerateDataKeyPair",
          "kms:ListGrants",
          "kms:GetParametersForImport",
          "kms:Encrypt",
          "kms:GetKeyRotationStatus",
          "kms:DescribeKey"
        ]
        Effect   = "Allow"
        Resource = "arn:aws:kms:*:${local.account_id}:key/*"
      },
      {
        Sid = "KMSGrantAndReEncryptActions"
        Action = [
          "kms:CreateGrant",
          "kms:RevokeGrant",
          "kms:ReEncryptTo"
        ]
        Effect   = "Allow"
        Resource = "arn:aws:kms:*:${local.account_id}:key/*"
        Condition = {
          Bool = {
            "kms:GrantIsForAWSResource" = "true"
          }
        }
      }
    ]
  })

  #checkov:skip=CKV_AWS_288: "Ensure IAM policies does not allow data exfiltration": "Skipping this for simplicity"
  #checkov:skip=CKV_AWS_289: "Ensure IAM policies does not allow permissions management / resource exposure without constraints": "Skipping this for simplicity"
  #checkov:skip=CKV_AWS_290: "Ensure IAM policies does not allow write access without constraints": "Skipping this for simplicity"
  #checkov:skip=CKV_AWS_355: "Ensure no IAM policies documents allow "*" as a statement's resource for restrictable actions": "Skipping this for simplicity"
}

resource "aws_iam_policy" "project_policy_datazone" {

  name = "${var.APP}-${var.ENV}-project-role-policy-datazone"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "datazone:ListEnvironmentBlueprintConfigurationSummaries",
          "datazone:ListEnvironmentBlueprintConfigurations",
          "datazone:DeleteEnvironmentBlueprint",
          "datazone:RejectSubscriptionRequest",
          "datazone:AcceptPredictions",
          "datazone:AddPolicyGrant",
          "datazone:UpdateEnvironment",
          "datazone:RefreshToken",
          "datazone:UpdateRule",
          "datazone:DeleteProjectMembership",
          "datazone:ListProjectMemberships",
          "datazone:GetEnvironmentCredentials",
          "datazone:UpdateProject",
          "datazone:ListEnvironments",
          "datazone:GetEnvironmentActionLink",
          "datazone:CreateDomain",
          "datazone:DeleteProject",
          "datazone:DeleteListing",
          "datazone:CreateDataSource",
          "datazone:UpdateEnvironmentAction",
          "datazone:CreateDomainUnit",
          "datazone:ListDataProductRevisions",
          "datazone:GetSubscriptionTarget",
          "datazone:ListLinkedTypes",
          "datazone:DeleteSubscriptionGrant",
          "datazone:DeleteEnvironmentProfile",
          "datazone:CreateFormType",
          "datazone:ListSubscriptionGrants",
          "datazone:GetEnvironmentBlueprintConfiguration",
          "datazone:ListDomainUnitsForParent",
          "datazone:ValidatePassRole",
          "datazone:DeleteFormType",
          "datazone:UpdateEnvironmentProfile",
          "datazone:ListDataSources",
          "datazone:ListMetadataGenerationRuns",
          "datazone:AssociateEnvironmentRole",
          "datazone:DeleteEnvironmentAction",
          "datazone:DeleteEnvironment",
          "datazone:ListDataSourceRuns",
          "datazone:ListAssetFilters",
          "datazone:CreateAssetType",
          "datazone:CreateSubscriptionGrant",
          "datazone:ProvisionDomain",
          "datazone:CreateEnvironmentBlueprint",
          "datazone:AcceptSubscriptionRequest",
          "datazone:GetSubscriptionGrant",
          "datazone:CancelSubscription",
          "datazone:ListSubscriptionRequests",
          "datazone:ListSubscriptions",
          "datazone:PutEnvironmentBlueprintConfiguration",
          "datazone:CreateListingChangeSet",
          "datazone:ListEntityOwners",
          "datazone:GetGlossary",
          "datazone:ListProjectProfiles",
          "datazone:GetProjectProfile",
          "datazone:SsoLogout",
          "datazone:CancelMetadataGenerationRun",
          "datazone:GetRule",
          "datazone:SearchGroupProfiles",
          "datazone:SearchRules",
          "datazone:DeleteGlossary",
          "datazone:PostLineageEvent",
          "datazone:ListPolicyGrants",
          "datazone:DeleteEnvironmentBlueprintConfiguration",
          "datazone:GetGlossaryTerm",
          "datazone:CreateEnvironment",
          "datazone:DeleteConnection",
          "datazone:RemovePolicyGrant",
          "datazone:Search",
          "datazone:UpdateUserProfile",
          "datazone:ListDataSourceRunActivities",
          "datazone:GetDomainUnit",
          "datazone:DeleteProjectProfile",
          "datazone:CreateProjectProfile",
          "datazone:RevokeSubscription",
          "datazone:GetListing",
          "datazone:CreateAsset",
          "datazone:ListEnvironmentProfiles",
          "datazone:GetUpdateEligibility",
          "datazone:GetAssetFilter",
          "datazone:GetDataSource",
          "datazone:CreateSubscriptionTarget",
          "datazone:ListWarehouseMetadata",
          "datazone:GetEnvironmentAction",
          "datazone:CreateDataProductRevision",
          "datazone:GetEnvironmentProfile",
          "datazone:DeleteSubscriptionRequest",
          "datazone:RejectPredictions",
          "datazone:CreateUserProfile",
          "datazone:DeleteTimeSeriesDataPoints",
          "datazone:StopMetadataGenerationRun",
          "datazone:CreateEnvironmentAction",
          "datazone:CreateEnvironmentProfile",
          "datazone:UpdateGroupProfile",
          "datazone:CreateGroupProfile",
          "datazone:GetMetadataGenerationRun",
          "datazone:ListGroupsForUser",
          "datazone:UpdateEnvironmentDeploymentStatus",
          "datazone:GetAssetType",
          "datazone:UpdateEnvironmentBlueprint",
          "datazone:ListJobRuns",
          "datazone:SearchListings",
          "datazone:ListAccountEnvironments",
          "datazone:PostTimeSeriesDataPoints",
          "datazone:GetProject",
          "datazone:DeleteDataProduct",
          "datazone:CreateGlossaryTerm",
          "datazone:ListSubscriptionTargets",
          "datazone:ListLineageNodeHistory",
          "datazone:SearchTypes",
          "datazone:UpdateDomain",
          "datazone:GetGroupProfile",
          "datazone:UpdateSubscriptionTarget",
          "datazone:ListEnvironmentActions",
          "datazone:ListAssetRevisions",
          "datazone:CreateGlossary",
          "datazone:RemoveEntityOwner",
          "datazone:UpdateSubscriptionGrantStatus",
          "datazone:GetAsset",
          "datazone:GetSubscriptionRequestDetails",
          "datazone:GetDataProduct",
          "datazone:GetLineageNode",
          "datazone:GetDomain",
          "datazone:CreateRule",
          "datazone:CreateDataProduct",
          "datazone:CreateAssetRevision",
          "datazone:StartDataSourceRun",
          "datazone:UpdateSubscriptionRequest",
          "datazone:ListRules",
          "datazone:UpdateConnection",
          "datazone:UpdateGlossaryTerm",
          "datazone:DeleteAssetFilter",
          "datazone:SearchUserProfiles",
          "datazone:GetSubscriptionEligibility",
          "datazone:GetJobRun",
          "datazone:ListTimeSeriesDataPoints",
          "datazone:ListDomains",
          "datazone:ListTagsForResource",
          "datazone:AddEntityOwner",
          "datazone:CreateAssetFilter",
          "datazone:BatchPutLinkedTypes",
          "datazone:DeleteAsset",
          "datazone:DeleteDomain",
          "datazone:GetDataSourceRun",
          "datazone:UpdateEnvironmentConfiguration",
          "datazone:DeleteDomainUnit",
          "datazone:DeleteGlossaryTerm",
          "datazone:DeleteDataSource",
          "datazone:DeleteAssetType",
          "datazone:UpdateDataSource",
          "datazone:GetLineageEvent",
          "datazone:SsoLogin",
          "datazone:UpdateDomainUnit",
          "datazone:GetSubscription",
          "datazone:UpdateDataSourceRunActivities",
          "datazone:GetUserProfile",
          "datazone:StartMetadataGenerationRun",
          "datazone:ListEnvironmentBlueprints",
          "datazone:CreateProjectMembership",
          "datazone:UpdateAssetFilter",
          "datazone:GetEnvironmentBlueprint",
          "datazone:ListLineageEvents",
          "datazone:ListProjects",
          "datazone:BatchDeleteLinkedTypes",
          "datazone:DisassociateEnvironmentRole",
          "datazone:CreateProject",
          "datazone:UpdateProjectProfile",
          "datazone:ListNotifications",
          "datazone:GetFormType",
          "datazone:ListConnections",
          "datazone:GetTimeSeriesDataPoint",
          "datazone:DeleteRule",
          "datazone:GetConnection",
          "datazone:GetDomainSharingPolicy",
          "datazone:UpdateGlossary",
          "datazone:CreateSubscriptionRequest",
          "datazone:DeleteSubscriptionTarget",
          "datazone:CreateConnection",
          "datazone:GetDomainExecutionRoleCredentials",
          "datazone:GetEnvironment"
        ]
        Effect   = "Allow"
        Resource = "*"
      }
    ]
  })

  #checkov:skip=CKV_AWS_288: "Ensure IAM policies does not allow data exfiltration": "Skipping this for simplicity"
  #checkov:skip=CKV_AWS_289: "Ensure IAM policies does not allow permissions management / resource exposure without constraints": "Skipping this for simplicity"
  #checkov:skip=CKV_AWS_290: "Ensure IAM policies does not allow write access without constraints": "Skipping this for simplicity"
  #checkov:skip=CKV_AWS_355: "Ensure no IAM policies documents allow "*" as a statement's resource for restrictable actions": "Skipping this for simplicity"
}

resource "aws_iam_policy" "project_policy_ssm" {

  name = "${var.APP}-${var.ENV}-project-role-policy-ssm"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "ssm:GetParameter",
        ]
        Effect   = "Allow"
        Resource = "*"
      }
    ]
  })

  #checkov:skip=CKV_AWS_288: "Ensure IAM policies does not allow data exfiltration": "Skipping this for simplicity"
  #checkov:skip=CKV_AWS_289: "Ensure IAM policies does not allow permissions management / resource exposure without constraints": "Skipping this for simplicity"
  #checkov:skip=CKV_AWS_290: "Ensure IAM policies does not allow write access without constraints": "Skipping this for simplicity"
  #checkov:skip=CKV_AWS_355: "Ensure no IAM policies documents allow "*" as a statement's resource for restrictable actions": "Skipping this for simplicity"
}

resource "aws_iam_policy" "project_policy_glue" {

  name = "${var.APP}-${var.ENV}-project-role-policy-glue"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "glue:GetCrawler",
          "glue:GetTableOptimizer",
          "glue:BatchGetDevEndpoints",
          "glue:GetTableVersions",
          "glue:GetPartitions",
          "glue:GetMLTransform",
          "glue:ListUsageProfiles",
          "glue:GetDevEndpoint",
          "glue:GetTrigger",
          "glue:GetJobRun",
          "glue:GetResourcePolicies",
          "glue:GetIntegrationResourceProperty",
          "glue:GetCustomEntityType",
          "glue:GetDataQualityResult",
          "glue:GetJobs",
          "glue:ListStatements",
          "glue:GetTriggers",
          "glue:GetWorkflowRun",
          "glue:GetGeneratedCode",
          "glue:ListCrawls",
          "glue:ListCustomEntityTypes",
          "glue:GetPartitionIndexes",
          "glue:GetMapping",
          "glue:GetPartition",
          "glue:GetCatalog",
          "glue:ListColumnStatisticsTaskRuns",
          "glue:GetEntityRecords",
          "glue:ListSchemaVersions",
          "glue:GetDataQualityModel",
          "glue:GetClassifiers",
          "glue:GetDataQualityRuleRecommendationRun",
          "glue:GetColumnStatisticsTaskSettings",
          "glue:GetCatalogImportStatus",
          "glue:BatchGetBlueprints",
          "glue:GetTableVersion",
          "glue:GetConnection",
          "glue:GetDashboardUrl",
          "glue:ListSchemas",
          "glue:GetCompletion",
          "glue:DescribeIntegrations",
          "glue:GetColumnStatisticsTaskRun",
          "glue:ListDataQualityRuleRecommendationRuns",
          "glue:GetRegistry",
          "glue:BatchGetPartition",
          "glue:ListJobs",
          "glue:GetTags",
          "glue:GetTable",
          "glue:GetDatabase",
          "glue:ListJobUpgradeAnalyses",
          "glue:GetDataflowGraph",
          "glue:BatchGetCrawlers",
          "glue:GetSession",
          "glue:QuerySchemaVersionMetadata",
          "glue:ListDataQualityResults",
          "glue:GetPlan",
          "glue:ListCrawlers",
          "glue:GetColumnStatisticsForPartition",
          "glue:GetJobRuns",
          "glue:SearchTables",
          "glue:GetDataCatalogEncryptionSettings",
          "glue:CheckSchemaVersionValidity",
          "glue:GetWorkflowRunProperties",
          "glue:DescribeInboundIntegrations",
          "glue:GetJobUpgradeAnalysis",
          "glue:GetSchema",
          "glue:GetSecurityConfiguration",
          "glue:GetResourcePolicy",
          "glue:GetUserDefinedFunction",
          "glue:GetCatalogs",
          "glue:GetBlueprint",
          "glue:BatchGetTableOptimizer",
          "glue:GetColumnStatisticsForTable",
          "glue:GetUserDefinedFunctions",
          "glue:GetClassifier",
          "glue:GetSchemaByDefinition",
          "glue:ListWorkflows",
          "glue:GetTables",
          "glue:GetSchemaVersionsDiff",
          "glue:ListBlueprints",
          "glue:ListTableOptimizerRuns",
          "glue:GetDataQualityRuleset",
          "glue:GetDevEndpoints",
          "glue:BatchGetWorkflows",
          "glue:GetColumnStatisticsTaskRuns",
          "glue:ListDevEndpoints",
          "glue:BatchGetJobs",
          "glue:GetStatement",
          "glue:ListRegistries",
          "glue:GetIntegrationTableProperties",
          "glue:GetJob",
          "glue:GetWorkflow",
          "glue:GetBlueprintRun",
          "glue:GetConnections",
          "glue:GetCrawlers",
          "glue:GetBlueprintRuns",
          "glue:ListMLTransforms",
          "glue:ListDataQualityRulesets",
          "glue:GetJobBookmark",
          "glue:GetMLTransforms",
          "glue:ListSessions",
          "glue:GetMLTaskRuns",
          "glue:ListTriggers",
          "glue:GetSecurityConfigurations",
          "glue:GetDatabases",
          "glue:GetMLTaskRun",
          "glue:GetUsageProfile",
          "glue:GetSchemaVersion",
          "glue:BatchGetTriggers",
          "glue:ListDataQualityRulesetEvaluationRuns",
          "glue:BatchGetCustomEntityTypes",
          "glue:GetDataQualityRulesetEvaluationRun",
          "glue:GetWorkflowRuns",
          "glue:GetCrawlerMetrics",
          "glue:GetDataQualityModelResult"
        ]
        Effect   = "Allow"
        Resource = "*"
      }
    ]
  })

  #checkov:skip=CKV_AWS_288: "Ensure IAM policies does not allow data exfiltration": "Skipping this for simplicity"
  #checkov:skip=CKV_AWS_289: "Ensure IAM policies does not allow permissions management / resource exposure without constraints": "Skipping this for simplicity"
  #checkov:skip=CKV_AWS_290: "Ensure IAM policies does not allow write access without constraints": "Skipping this for simplicity"
  #checkov:skip=CKV_AWS_355: "Ensure no IAM policies documents allow "*" as a statement's resource for restrictable actions": "Skipping this for simplicity"
}

resource "aws_iam_policy" "project_policy_lake_formation" {

  name = "${var.APP}-${var.ENV}-project-role-policy-lake-formation"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "lakeformation:ListLFTagExpressions",
          "lakeformation:SearchDatabasesByLFTags",
          "lakeformation:GetDataAccess",
          "lakeformation:GetDataCellsFilter",
          "lakeformation:GetWorkUnits",
          "lakeformation:RegisterResource",
          "lakeformation:UpdateLakeFormationIdentityCenterConfiguration",
          "lakeformation:ListPermissions",
          "lakeformation:CommitTransaction",
          "lakeformation:GetLFTagExpression",
          "lakeformation:CreateLakeFormationOptIn",
          "lakeformation:SearchTablesByLFTags",
          "lakeformation:DeleteLakeFormationOptIn",
          "lakeformation:UpdateLFTag",
          "lakeformation:GetLFTag",
          "lakeformation:UpdateTableStorageOptimizer",
          "lakeformation:GetResourceLFTags",
          "lakeformation:ListResources",
          "lakeformation:CreateLFTag",
          "lakeformation:GetQueryStatistics",
          "lakeformation:GetDataLakeSettings",
          "lakeformation:CreateDataCellsFilter",
          "lakeformation:UpdateResource",
          "lakeformation:StartQueryPlanning",
          "lakeformation:GetDataLakePrincipal",
          "lakeformation:ListLakeFormationOptIns",
          "lakeformation:RegisterResourceWithPrivilegedAccess",
          "lakeformation:DeleteLFTagExpression",
          "lakeformation:CreateLFTagExpression",
          "lakeformation:UpdateDataCellsFilter",
          "lakeformation:CancelTransaction",
          "lakeformation:ExtendTransaction",
          "lakeformation:ListDataCellsFilter",
          "lakeformation:CreateLakeFormationIdentityCenterConfiguration",
          "lakeformation:GetEffectivePermissionsForPath",
          "lakeformation:ListTransactions",
          "lakeformation:DeleteObjectsOnCancel",
          "lakeformation:ListLFTags",
          "lakeformation:GetWorkUnitResults",
          "lakeformation:ListTableStorageOptimizers",
          "lakeformation:GetQueryState",
          "lakeformation:StartTransaction",
          "lakeformation:UpdateTableObjects",
          "lakeformation:DescribeResource",
          "lakeformation:DescribeLakeFormationIdentityCenterConfiguration",
          "lakeformation:UpdateLFTagExpression",
          "lakeformation:DeleteLFTag",
          "lakeformation:GetTableObjects",
          "lakeformation:DeregisterResource",
          "lakeformation:DeleteDataCellsFilter",
          "lakeformation:DeleteLakeFormationIdentityCenterConfiguration",
          "lakeformation:DescribeTransaction"
        ]
        Effect   = "Allow"
        Resource = "*"
      }
    ]
  })

  #checkov:skip=CKV_AWS_288: "Ensure IAM policies does not allow data exfiltration": "Skipping this for simplicity"
  #checkov:skip=CKV_AWS_289: "Ensure IAM policies does not allow permissions management / resource exposure without constraints": "Skipping this for simplicity"
  #checkov:skip=CKV_AWS_290: "Ensure IAM policies does not allow write access without constraints": "Skipping this for simplicity"
  #checkov:skip=CKV_AWS_355: "Ensure no IAM policies documents allow "*" as a statement's resource for restrictable actions": "Skipping this for simplicity"
}

# Producer Role

resource "aws_iam_role_policy_attachment" "producer_role_attachment_s3" {

  role       = split(":role/", local.PRODUCER_ROLE)[1]
  policy_arn = aws_iam_policy.project_policy_s3.arn
}

resource "aws_iam_role_policy_attachment" "producer_role_attachment_s3_tables" {

  role       = split(":role/", local.PRODUCER_ROLE)[1]
  policy_arn = aws_iam_policy.project_policy_s3_tables.arn
}

resource "aws_iam_role_policy_attachment" "producer_role_attachment_kms" {

  role       = split(":role/", local.PRODUCER_ROLE)[1]
  policy_arn = aws_iam_policy.project_policy_kms.arn
}

resource "aws_iam_role_policy_attachment" "producer_role_attachment_datazone" {

  role       = split(":role/", local.PRODUCER_ROLE)[1]
  policy_arn = aws_iam_policy.project_policy_datazone.arn
}

resource "aws_iam_role_policy_attachment" "producer_role_attachment_ssm" {

  role       = split(":role/", local.PRODUCER_ROLE)[1]
  policy_arn = aws_iam_policy.project_policy_ssm.arn
}

resource "aws_iam_role_policy_attachment" "producer_role_attachment_glue" {

  role       = split(":role/", local.PRODUCER_ROLE)[1]
  policy_arn = aws_iam_policy.project_policy_glue.arn
}

resource "aws_iam_role_policy_attachment" "producer_role_attachment_lake_formation" {

  role       = split(":role/", local.PRODUCER_ROLE)[1]
  policy_arn = aws_iam_policy.project_policy_lake_formation.arn
}

# Consumer Role

resource "aws_iam_role_policy_attachment" "consumer_role_attachment_s3" {

  role       = split(":role/", local.CONSUMER_ROLE)[1]
  policy_arn = aws_iam_policy.project_policy_s3.arn
}

resource "aws_iam_role_policy_attachment" "consumer_role_attachment_s3_tables" {

  role       = split(":role/", local.CONSUMER_ROLE)[1]
  policy_arn = aws_iam_policy.project_policy_s3_tables.arn
}

resource "aws_iam_role_policy_attachment" "consumer_role_attachment_kms" {

  role       = split(":role/", local.CONSUMER_ROLE)[1]
  policy_arn = aws_iam_policy.project_policy_kms.arn
}

resource "aws_iam_role_policy_attachment" "consumer_role_attachment_datazone" {

  role       = split(":role/", local.CONSUMER_ROLE)[1]
  policy_arn = aws_iam_policy.project_policy_datazone.arn
}

resource "aws_iam_role_policy_attachment" "consumer_role_attachment_ssm" {

  role       = split(":role/", local.CONSUMER_ROLE)[1]
  policy_arn = aws_iam_policy.project_policy_ssm.arn
}

resource "aws_iam_role_policy_attachment" "consumer_role_attachment_glue" {

  role       = split(":role/", local.CONSUMER_ROLE)[1]
  policy_arn = aws_iam_policy.project_policy_glue.arn
}

resource "aws_iam_role_policy_attachment" "consumer_role_attachment_lake_formation" {

  role       = split(":role/", local.CONSUMER_ROLE)[1]
  policy_arn = aws_iam_policy.project_policy_lake_formation.arn
}