# Solutions Deployment Guide

## Table of Contents

- [Pre-requisites](#deployment-pre-requisite)
  - [Packages](#packages)
  - [AWS CLI setup](#aws-cli-setup)
  - [Navigate to the project root](#navigate-to-the-project-root)
  - [Environment setup](#environment-setup)
- [Deployment steps](#deployment-steps)
- [Troubleshooting](#troubleshooting)

## Deployment Pre-requisite

### Packages

In order to execute this deployment, please ensure you have installed the following packages on the machine from which you're deploying the solution:

- [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)

_Note: Make sure that the latest AWS CLI version is installed. If not, some functionalities won't be deployed correctly._

- [Terraform >= 1.8.0](https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli)
- [Git CLI](https://git-scm.com/downloads)
- [Python >= 3.10](https://www.python.org/downloads/)
- [PIP >= 25.0.1](https://pypi.org/project/pip/)
- [make](https://www.gnu.org/software/make/)
- [jq](https://stedolan.github.io/jq/)

_Note: Make sure the machine you are deploying from has up to 15 GB free space to deploy the entire solution. We have included a clean up script (module 21) to clean up the cache in the local machine after deployment._

> [!CAUTION]
> We are using the latest version 5 for the AWS Terraform provider (v 5.100) in every module of this solution. Please do not update providers to the latest version 6 as it will break the deployment process.

### Navigate to the project root

1. Open your local terminal and navigate to the `data-platform` folder:

```
cd data-platform
```

### Environment setup

#### Input variable names used in the prototype and their meanings

> [!CAUTION]
> Please do not use '-' sign in app or environment name in this step. This will break SQL quesry executions in the Datalake modules.

```
# 12 digit AWS account ID to deploy resources to
AWS_ACCOUNT_ID

# The application name that is used to name resources
# It is best to use a short value to avoid resource name length limits
# Example: daivi
APP_NAME

# The environment name that is used to name resources and to determine
# the value of environment-specific configurations.
# It is best to use a short value to avoid resource name length limits
# Select environment names that are unique.
# Examples: quid7, mxr9, your initials with a number
ENV_NAME

# Primary AWS region to deploy application resources to
# Example: us-east-1
AWS_PRIMARY_REGION

# Secondary AWS region to deploy application resources to
# Example: us-west-2
AWS_SECONDARY_REGION

# The IAM role name used to login to the AWS Console
# This role will be granted Lake Formation admin access to query
# Glue databases via Athena and the AWS Console
# Example: Admin
ADMIN_ROLE
```

<br>

Environment Setup Steps:

### Prerequisites: Create datapipeline IAM User

Before running any make targets, create an IAM user named `datapipeline` with `AdministratorAccess` policy. This user is used to run all deployment commands, Glue jobs, Redshift queries, and Lake Formation administration.

1. Go to IAM Console → Users → Create user
2. User name: `datapipeline`
3. Attach the `AdministratorAccess` managed policy
4. Create access keys for CLI access

### 1. Deployment Role

Use the `datapipeline` IAM user credentials to configure the AWS CLI. This user will be used to run all make targets.

To setup your aws-cli with the datapipeline credentials run the following command:

```
aws configure
```

Alternatively, you can manually modify the following files:

`~/.aws/config`

`~/.aws/credentials`

Alternatively, you can manually initialize the terminal with STS credentials for the role, by obtaining temporary STS credentials from your administrator.

```
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_SESSION_TOKEN=...
```

2. **Initialization**: From your terminal, go to the `data-platform` root directory and execute the following command.
   This command will run a wizard that will ask you to provide a value for all of the configuration settings documented above.
   It will perform a search/replace on the project files so that they use the values you provide.

```
make init
```

3. **Set Up Terraform Backend**: Execute the following command to set up S3 buckets to store the project's Terraform state.

```
make deploy-tf-backend-cf-stack
```

## Deployment Steps

The Makefile contains a "deploy-all" target, but we strongly recommend tha you "**DO NOT**" use this make target. We do not recommend deploying the solution in one go. This is due to the time needed for some make targets to initialize, warm-up and execute correctly. For example, job schedulers need time to properly set up their triggers. Also some make targets have linear dependency on other make targets. Deploying it in one go will likely cause configuration errors since some deployed make targets may not be fully functional yet and thus, not ready to be used.

Therefore, we recommend deploying the make targets incrementally, one make target at a time, to allow each make target to execute successfully and be fully operational before the next make target is executed:

1. Deploy each make target one at a time
2. Wait for each make target to complete
3. Verify that the make target is fully operational
4. Only then proceed to the next make target

The solution consists of a number of modules. Each module consists of a number of make targets. Please deploy the modules in the order mentioned below. Each module has a make target, ex: deploy-foundation. Please "**DO NOT**" invoke the make target for a module. Instead invoke individual make targets under each module in the order they are mentioned, waiting for each make target to complete successfully before moving to the next make target.

You will need to deploy the following modules in order to deploy the whole solution.

| Order | Module                                                                                                        |
| ----- | --------------------------------------------------------------------------------------------------------------|
| 1     | [Foundation](#1-foundation)                                                                                   |
| 2     | [IAM Identity Center](#2-iam-identity-center)                                                                 |
| 3     | [Sagemaker Domain](#3-sagemaker-domain)                                                                       |
| 4     | [Glue Iceberg Jar File](#4-glue-iceberg-jar-file)                                                             |
| 5     | [Lake Formation](#5-lake-formation)                                                                           |
| 6     | [Athena](#6-athena)                                                                                           |
| 7     | [Financial Advisor Data Lake](#7-financial-advisor-data-lake)                                                  |
| 8     | [Sagemaker Projects](#8-sagemaker-projects)                                                                   |
| 9     | [Sagemaker Project Configuration](#9-sagemaker-project-configuration)                                        |
| 10    | [Redshift Views](#10-redshift-views)                                                                          |
| 11    | [Quicksight Subscription](#11-quicksight-subscription)                                                        |
| 12    | [Quicksight Visualization](#12-quicksight-visualization)                                                      |
| 13    | [Post Deployment Testing](#13-post-deployment-testing)                                                        |
| 14    | [Clean Up Cache](#14-clean-up-cache)                                                                          |

---

## 1. **Foundation**

The foundation module deploys the foundational resources, such as KMS Keys, IAM Roles and S3 Buckets that other modules need. We are provisioning KMS Keys and IAM Roles in a separate module and passing them as parameters to other modules, as in many customer organizations the central cloud team provisions these resources and allows the application teams to use these resources in their applications. We recommend that you review the IAM roles in foundation module with your cloud infrastructure team and cloud security team, update them as necessary, before you provision them in your environment. You **MUST** deploy the make targets for this module first before deploying make targets for other modules. Please execute the following make targets in order.

#### To deploy the module:

```
make deploy-kms-keys
make deploy-iam-roles
make deploy-buckets
make deploy-vpc
make build-msk-data-generator-lambda-layer-zip
make deploy-msk
```

| Target             | Result                                                                          | Verification                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ------------------ | ------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| deploy-kms-keys    | Provisions KMS keys used by different AWS services                              | Following KMS keys and aliases are created: <br> 1. {app}-{env}-secrets-manager-secret-key <br> 2. {app}-{env}-systems-manager-secret-key <br> 3. {app}-{env}-s3-secret-key <br> 4. {app}-{env}-glue-secret-key <br> 5. {app}-{env}-athena-secret-key <br> 6. {app}-{env}-event-bridge-secret-key <br> 7. {app}-{env}-cloudwatch-secret-key <br> 8. {app}-{env}-datazone-secret-key <br> 9. {app}-{env}-ebs-secret-key <br> 10. {app}-{env}-msk-secret-key <br> 11. {app}-{env}-dynamodb-secret-key                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| deploy-iam-roles   | Provisions IAM roles used by different modules                                  | Following IAM roles are created: <br> 1. {app}-{env}-glue-role <br> 2. {app}-{env}-lakeformation-service-role <br> 3. {app}-{env}-eventbridge-role <br> 4. {app}-{env}-lambda-billing-trigger-role <br> 5. {app}-{env}-lambda-inventory-trigger-role <br> 6. {app}-{env}-splunk-role <br> 7. {app}-{env}-event-bridge-role <br> 8. {app}-{env}-sagemaker-role <br> 9. {app}-{env}-datazone-domain-execution-role <br> 10. {app}-{env}-quicksight-service-role                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| deploy-buckets     | Deploy S3 buckets needed by different modules                                   | Following S3 buckets are created: <br> 1. {account}-{app}-{env}-glue-scripts <br> 2. {account}-{app}-{env}-glue-jars <br> 3. {account}-{app}-{env}-glue-spark-logs <br> 4. {account}-{app}-{env}-glue-temp <br> 5. {account}-{app}-{env}-athena-output <br> 6. {account}-{app}-{env}-amazon-sagemaker <br> 7. {account}-{app}-{env}-smus-project-cfn-template |
| deploy-vpc         | Deploy a common vpc to be used for the project                                  | Following resource are creates: <br> 1. {app}-{env}-vpc (10.38.0.0/16) <br> 2. private subntes (3) <br> 3. public subnets (3) <br> 4. {app}-{env}-public-rt public route table with 3 public sunet associated and route to internet gateway <br> 5. {app}-{env}-private-rt private route table with 3 private route table association and route to NAT gateway <br> 6. A {app}-{env}-nat-gateway <br> 7. A {app}-{env}-igw internet gateway attached to vpc                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| build-msk-data-generator-lambda-layer-zip | builds a zip for msk data generator lambda dependencies                             | verify dependencies_layer.zip exists at iac/roots/foundation/msk-serverless/data-generator                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| deploy-msk         | Deploy MSK cluster along with kafka tool on ec2 and lambda based data generator | 1. Verify {app}-{env}-msk-cluster is in active status <br> <br> 2. verify {app}-{env}-msk-producer-lambda lambda function <br> <br> 3. EC2 instance deployed with kafka ui tool --> {app}-{env}-msk-client. To view the MSK cluster topics and messages, update the ec2 security group to allow traffic from your public ip and access the UI on EC2 public ip on port 9000                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |

## 2. **IAM Identity Center**

The IAM Identity Center module enables deployment of either:

- An account-specific instance (isolated to a single AWS account)
- An organization-wide instance (managed through AWS Organizations)

Choose the deployment type that best suits your organization's requirements.[Review AWS Documentation](https://docs.aws.amazon.com/singlesignon/latest/userguide/identity-center-instances.html) to understand the differences between Account-level versus Organization-level Identity Center

#### Before deploying this step:

**Important Note**: Only one instance can be deployed across all regions, and it must be either Account-level or Organization-level.

#### To deploy the account level identity center configuration:

```
make deploy-idc-acc
```

#### To deploy the organization level identity center configuration:

**Note**: This step is only applied to organization-level IAM Identity Center. For account-level or standalone instance, this step has been automated as part of the deployment process.
Before configuring Identity Center for organization-level using make targets:

1. Enable the Organization-level manually on the IAM Identity Center Console

- Navigate to IAM Identity Center in the console
- For organization-level: Select "Enable" > _Enable IAM Identity Center with AWS Organizations_ > "Enable"

2. Ensure no existing Identity Center instance is running

- Must delete previous instance before deploying new one
- Currently no programmatic support is available to enable Identity Center through IaC

```
make deploy-idc-org
```

| Target         | Result                                                                                 | Verification                                                                                                                                                                                                                                                                                                                                                        |
| -------------- | -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| deploy-idc-acc | Deploy IAM Identity Center groups, users (Account-level)                               | Following groups are created in Identity Center: <br> 1. Admin <br> 2. Domain Owner <br> 3. Project Owner <br> 4. Project Coordinator <br> <br> Following users are created in Identity Center: <br> 1. chris-bakony-admin@example.com <br> 2. ann-chouvey-downer@example.com <br> 3. lois-lanikini-powner@example.com <br> 4. ben-doverano-contributor@example.com |
| deploy-idc-org | Provisions IAM Identity Center groups, users, and permission sets (Organization-level) | Following groups are created in Identity Center: <br> 1. Admin <br> 2. Domain Owner <br> 3. Project Owner <br> 4. Project Coordinator <br> <br> Following users are created in Identity Center: <br> 1. chris-bakony-admin@example.com <br> 2. ann-chouvey-downer@example.com <br> 3. lois-lanikini-powner@example.com <br> 4. ben-doverano-contributor@example.com |

---

#### Two-Factor Authentication:

IAM Identity Center is configured to require two-factor authentication. We recommend you retain the two-factor authentication configured. In case, you would like **disable two-factor authentication** in your sandbox account to make it easy for you to login to Sagemaker Unified Studio, you can otherwise run the following deployment command after your IDC instance has been created:

```
make disable-mfa
```

We do not recommend disabling multi-factor authentication. However, if you used the above commands to make it easy for you to explore the solution in a Sandbox account, we recommend that you enable multi-factor authentication once you have completed exploring the solution. We do not recommend disabling multi-factor authentication in development, test or production environment.

#### Setting Password for Users:

Execute the following steps to set up passwords for the users created in IAM Identity Center.

1. Click on "User" in left navigation panel
2. For each "User" in the list do the following
3. Click on the "Username" to go to the page for the user
4. Click on "Reset password" on top right
5. Selct the check box "Generate a one-time password and share the password with the user"
6. Click on "Reset password" button
7. It will show "One-time Password" window
8. Click on the square on left of the "one-time password" to copy the password to clipboard
9. Store the username and the one-time password in a file using your favorite editor. You will need this username and one-time password to login to Sagemaker and Datazone.

#### Useful Command to Delete a Previously Congifured Identity Center Instance (Don't Need to Execute the Following Commands):

If you need to delete a previously deployed Organization-level instance:

```
   aws organizations delete-organization
```

To delete Account-level Instance:

```
   # retrieve the instance ARN
   aws sso-admin list-instances

   # delete the account-level instance using retrieved ARN
   aws sso-admin delete-instance --instance-arn arn:aws:sso:<region>:<account-id>:instance/<instance-id>
```

### Using your Existing IAM Identity Center

If you have an existing IAM Identity Center instance (either in your current AWS account or in another accessible AWS account), you can reuse it instead of creating a new one. To integrate your existing instance with SageMaker Unified Studio and Datazone modules, you will need to store the user group mappings in AWS Systems Manager Parameter Store.

There are two methods to configure user groups for your deployment: Discovery (DYO) and Manual (BYO).

#### 1. Discovery Method (Discover-your-own IDC)

This method automatically discovers and maps existing IAM Identity Center groups to required roles.

The command expects four user groups in your IAM Identity Center:

- Admin
- Domain Owner
- Project Owner
- Project Contributor

##### Automatic User Assignment

The command handles various scenarios to ensure critical roles are always populated:

1. **For Admin, Domain Owner, and Project Owner groups:**
   - If the group doesn't exist: The deployer's email (caller identity) is automatically added
   - If the group exists but is empty: The deployer's email is automatically added
   - If the group exists and has users: The existing users are preserved
2. **For Project Contributor group:**
   - If the group doesn't exist: An empty list is created
   - If the group exists but is empty: The list remains empty
   - If the group exists and has users: The existing users are preserved

##### Why This Matters

This automatic user assignment is crucial because:

- Domain creation for SageMaker Unified Studio and Amazon Datazone requires at least one Domain Owner
- Projects creation requires at least one Project Owner
- By automatically adding the deployer to these roles when needed, the command ensures these requirements are met and prevents deployment failures

To use this method:

```
make deploy-dyo-idc
```

#### 2. Manual Method (Bring-your-own IDC)

This method allows manual configuration of user groups and their members, ideal for scenarios where:

- Your IAM Identity Center doesn't have groups matching our required group names
- You want to specify custom group memberships without modifying existing IAM Identity Center groups
- You prefer direct control over user assignments

#### Requirements

- A valid Identity Store ID
- At least one valid email for Domain Owner group
- At least one valid email for Project Owner group
- Admin and Project Contributor groups can be empty

To use this method:

```
make deploy-byo-idc
```

The command WILL:

- Prompt for your Identity Store ID
- Request email addresses for each group (Admin, Domain Owner, Project Contributor, Project Owner)
- Allow multiple emails per group (using comma or space separation)
- Validate email address formats
- Show a preview of the complete configuration
- Create/update the SSM parameter after confirmation

The command will NOT perform these critical validations:

- Verify if the provided Identity Store ID exists or is valid
- Check if the entered email addresses belong to actual users in your IAM Identity Center

⚠️ **User Responsibility:**

1. Ensure the Identity Store ID is correct
2. Verify all provided email addresses correspond to existing users in your IAM Identity Center

❗ **Warning:** Providing incorrect information (invalid Identity Store ID or non-existent users) will not cause immediate errors but will lead to failures in subsequent deployment steps when the system attempts to assign permissions to these users.

## 3. **Sagemaker Domain**

This module deploys a Sagemaker Domain for SageMaker Unified Studio, enabling relevant blueprints, and creating project profiles with relevant blueprints.

#### To deploy the module:

```
make deploy-domain-prereq
make deploy-domain
```

| Target               | Result                          | Verification                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| -------------------- | ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| deploy-domain        | Deploy Domain                   | Following Sagemaker resources are created <br> 1. Sagemaker domain called _Corporate_ <br> 2. Sagemaker blueprints are enabled under _Corporate_ domain <br> 3. Three Sagemaker project profiles are configured under _Corporate_ domain <br> 4. Login to Sagemaker Unified Studio for _Corporate_ domain using various user credentials created in _IAM Identity Center_ section and confirm that you are able to open the domain. When you login to Sagemaker Unified Studio, it will be ask you to enter usename and one-time password you had created in the _IAM Identity Center_ and it will ask you change the password. Please use a password with letter, numbers and special charaters and store the password in a file using your favorite editor. |

---

## 4. **Glue Iceberg Jar File**

This module downloads and deploys the glue runtime jar file that is needed for glue jobs to interact with Iceberg tables.

#### To deploy the module:

```
make deploy-glue-jars
```

| Target           | Result               | Verification                                                                                                                                |
| ---------------- | -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| deploy-glue-jars | Deploy Glue jar file | Verify that the iceberg jar file "s3-tables-catalog-for-iceberg-runtime-0.1.5.jar" is uploaded to S3 bucket "{app}-{env}-glue-jars-primary" |

---

## 5. **Lake Formation**

This module deploys lake formation configuration to create Glue catalog for s3tables, registers s3table bucket location with lake formation using lake formation service role, and grants Lake Formation permissions on the S3 Tables catalog to the Admin role, IAMAllowedPrincipals, and the datapipeline IAM user.

#### To deploy the module:

```
make set-up-lake-formation-admin-role
make create-glue-s3tables-catalog
make register-s3table-catalog-with-lake-formation
make grant-default-database-permissions
make drop-default-database
```

| Target                                       | Result                                                        | Verification                                                                                                                                                                                                                   |
| -------------------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| set-up-lake-formation-admin-role             | Sets Admin role and datapipeline user as Lake Formation admins | Verify in Lake Formation -> Administrative roles and tasks that both principals are listed as Data lake administrators                                                                                                         |
| create-glue-s3tables-catalog                 | Create Glue catalog for S3tables                              | Verify that the following Glue catalog is created in Lakeformation by opening "Data Catalog -> Catalogs": <br> 1. s3tablescatalog                                                                                              |
| register-s3table-catalog-with-lake-formation | Registers S3 table location with lake formation               | Verify that the s3table location is registered with Lakeformation by opening "Administration->Data lake locations" and finding an entry for the following data lake location: <br> 1. s3://tables:{region}:{account}:bucket/\* |
| grant-default-database-permissions           | Grants DROP permission on default database to Admin role      | Verify in Lake Formation -> Data permissions                                                                                                                                                                                   |
| drop-default-database                        | Drops the default Glue database                               | Verify default database no longer exists in Glue                                                                                                                                                                               |

> **Note:** `make drop-default-database` may return an "Access Denied" error if the default database does not exist or has already been dropped. This can be safely skipped.

## 6. **Athena**

This module deploys an athena workgroup.

#### To deploy the module:

```
make deploy-athena
```

| Target        | Result                  | Verification                                                               |
| ------------- | ----------------------- | -------------------------------------------------------------------------- |
| deploy-athena | Create Athena workgroup | Verify following Athena workgroup is created <br> 1. {app}-{env}-workgroup |

---

## 7. **Financial Advisor Data Lake**

This module deploys the financial advisor data lake, which loads 24 CSV data files into Iceberg tables on S3 table buckets using Glue batch data pipelines. It provisions S3 buckets, S3 table buckets with Iceberg tables, and Glue jobs to load 24 financial advisor datasets (clients, advisors, accounts, portfolios, securities, transactions, holdings, market data, performance, fees, goals, interactions, documents, compliance, research, articles, and more).

#### To deploy the module:

```
make deploy-financial-advisor-s3-glue-s3
make start-financial-advisor-glue-jobs
```

| Target                                                    | Result                                                                            | Verification                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| --------------------------------------------------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| deploy-financial-advisor-s3-glue-s3                       | Deploy financial advisor infrastructure                                           | Following S3 bucket is created: <br> 1. {account}-{app}-{env}-financial-advisor-s3-glue-s3-data <br><br> Following S3 table bucket is created: <br> 1. financial-advisor-s3table <br><br> Following Glue jobs are created (one per table): <br> 1. financial-advisor-load-clients <br> 2. financial-advisor-load-advisors <br> 3. financial-advisor-load-accounts <br> ... (24 total, one per CSV file) |
| start-financial-advisor-glue-jobs                         | Run all 24 financial advisor Glue jobs                                            | Verify that all glue jobs start. Wait for all glue jobs to complete                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |

---

## 8. **Sagemaker Projects**

This module deploys two Sagemaker projects, one for **Producer** and one for **Consumer**. When you execute the "deploy-producer-project" or "deploy-consumer-project" make target, it will launch 4 cloud formation stacks for each project one after other. After executing the "deploy-producer-project" make target, please open Cloud Formation console and monitor the 4 cloud formation stacks get created and completed. Only then, proceed to execute the "deploy-consumer-project" make target and monitor the 4 cloud formation stacks get created and completed. Only then, proceed to execute the remaining 2 make targets "extract-producer-info" and "extract-consumer-info".

> **Important:** SageMaker Projects must be deployed after the S3 Tables catalog and Financial Advisor Data Lake (Steps 5-7) so that the Redshift environment automatically discovers and mounts the `s3tablescatalog`.

#### To deploy the module:

```
make deploy-project-prereq
make deploy-producer-project (wait for 4 cloud formation stacks to complete)
make deploy-consumer-project (wait for 4 cloud formation stacks to complete)
make extract-producer-info
make extract-consumer-info
make grant-s3table-lakeformation-permissions
make set-up-redshift-lf-readonly-admin
```

| Target                  | Result                                       | Verification                                                                                                                                                                                                                       |
| ----------------------- | -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| deploy-project-prereq   | Provisions Pre-requisites for Projects       | Provisions Sagemaker foundational resources                                                                                                                                                                                        |
| deploy-producer-project | Provisions Producer Project                  | Provisions following Sagemaker projects: <br> 1. Producer <br> 2. Login to Sagemaker Unified Studio using "Project Owner" user with username containing "powner" and confirm that you see the producer project and you can open it |
| deploy-consumer-project | Provisions Consumer Project                  | Provisions following Sagemaker projects: <br> 1. Consumer <br> 2. Login to Sagemaker Unified Studio using "Project Owner" user with username containing "powner" and confirm that you see the consumer project and you can open it |
| extract-producer-info   | Extracts id and role of the project producer | Provisions following SSM Parameters: <br> 1. /{app}/{env}/sagemaker/producer/id <br> 2. /{app}/{env}/sagemaker/producer/role <br> 3. /{app}/{env}/sagemaker/producer/role-name                                                     |
| extract-consumer-info   | Extracts id and role of the project consumer | Provisions following SSM Parameters: <br> 1. /{app}/{env}/sagemaker/consumer/id <br> 2. /{app}/{env}/sagemaker/consumer/role <br> 3. /{app}/{env}/sagemaker/consumer/role-name                                                     |
| grant-s3table-lakeformation-permissions      | Grants ALL permissions on S3 Tables catalog to key principals | Verify in Lake Formation -> Data permissions that the producer role, consumer role, Admin role, datapipeline user, and QuickSight role have ALL access on the S3 Tables catalog, database, and tables |
| set-up-redshift-lf-readonly-admin            | Adds AWSServiceRoleForRedshift as Lake Formation read-only admin | Verify in Lake Formation -> Administrative roles and tasks that AWSServiceRoleForRedshift is listed as a Read-only administrator. This is required for Redshift to discover and access the S3 Tables catalog. |

---

## 9. **Sagemaker Project Configuration**

This module configures the Sagemaker Producer and Consumer Projects to load the Data Lakes into Lakehouse by granting project roles lake house permissions to the data lakes.

#### To deploy the module:

```
make deploy-project-config
```

| Target                                                | Result                                                                                                                   | Verification                                                                                                        |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------- |
| deploy-project-config                                 | Deploy Project Config                                                                                                    | Grants Lake Formation permissions to the producer project role and consumer project role to access the financial advisor data lake |
---

## 10. **Redshift Views**

This module creates Redshift tables and views in the producer project's Redshift Serverless workgroup. The views provide analytical perspectives over the financial advisor data lake, including advisor dashboards, client portfolios, AUM tracking, and more.

#### Prerequisites

- Financial Advisor Data Lake must be deployed and Glue jobs must have completed successfully (Step 7)
- Sagemaker Project Configuration must be deployed (Step 9)

#### To deploy the module:

```
make create-redshift-tables
make load-redshift-tables
make create-redshift-views-s3tables
make create-quicksight-tables
```

| Target                                       | Result                                                                                          | Verification                                                                                                     |
| -------------------------------------------- | ----------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| create-redshift-tables                       | Creates 4 Redshift tables (articles, client_reports, themes, theme_article_associations)        | Verify tables are created in the producer project's Redshift workgroup                                           |
| load-redshift-tables                         | Loads CSV data into the 4 Redshift tables using COPY command                                    | Verify data is loaded into the Redshift tables                                                                   |
| create-redshift-views-s3tables               | Creates views that query S3 Tables catalog for 20 tables and Redshift directly for 4 app tables | Verify views are created and can query data from both S3 Tables catalog and Redshift                             |
| create-quicksight-tables                     | Creates snapshot tables from Redshift views for QuickSight (e.g. qs_advisor_dashboard_summary)  | Verify tables prefixed with qs_ are created in Redshift                                                          |

> Note: To refresh QuickSight snapshot tables after data changes, run `make refresh-quicksight-tables`.

#### Grant Redshift Access

After deploying, connect to the Redshift workgroup in **Redshift Query Editor v2** as the `admin` superuser and run:

> **Note:** Replace `Admin` with the IAM role name you use to access the AWS Console (the same role you provided as `ADMIN_ROLE` during `make init`). If the GRANT statements fail with `user does not exist`, create the IAM role user in Redshift first:
> ```sql
> CREATE USER "IAMR:<your-admin-role-name>" PASSWORD DISABLE;
> ```

```sql
GRANT USAGE ON SCHEMA public TO "IAM:datapipeline";
GRANT SELECT ON ALL TABLES IN SCHEMA public TO "IAM:datapipeline";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO "IAM:datapipeline";
GRANT USAGE ON SCHEMA public TO "IAMR:Admin";
GRANT SELECT ON ALL TABLES IN SCHEMA public TO "IAMR:Admin";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO "IAMR:Admin";
```

---

## 11. **QuickSight Subscription**

This module deploys the Amazon QuickSight subscription.

#### To deploy the module:

```
make deploy-quicksight-subscription
```

| Target                         | Result                         | Verification                                                                                           |
| ------------------------------ | ------------------------------ | ------------------------------------------------------------------------------------------------------ |
| deploy-quicksight-subscription | Deploy QuickSight subscription | Log into the console and directly see the main QuickSight homepage and confirm subscription is created |

---

#### Important Limitation

Currently (as of March 2025), there is a known limitation when creating a QuickSight subscription via Terraform or AWS API:

- You cannot programmatically assign IAM roles or configure data sources during the initial subscription creation
- This requires a two-step deployment process - if you proceed to create QuickSight subscription through Terraform/API
- Refer to the documentation [here](https://docs.aws.amazon.com/quicksight/latest/APIReference/API_CreateAccountSubscription.html)

## 12. **QuickSight Visualization**

This module deploys datasource, datasets and dashboard visualization for QuickSight.

#### Before deploying this step:

- RUM tables must be created and loaded (see below)
- Once the subscription is created, navigate to: QuickSight → Manage QuickSight → Permissions → AWS resources
- Choose "Use an existing role"
- Select {app}-{env}-quicksight-service-role
- Note: The quicksight-service-role is a custom IAM role configured with least-privilege access to:
  - Amazon Athena
  - AWS Glue Catalog
  - Amazon S3
  - AWS Lake Formation
- After IAM configuration is completed, deploy the QuickSight datasets and dashboards

> 💡 **CodeBuild CI/CD path:** This manual console step is not required. The VPC connection Terraform resource passes `role_arn` directly, so the account-level default role does not need to be set.

#### Create RUM Tables and Load Data

```
make create-rum-tables
make load-rum-data
```

| Target                    | Result                                                              | Verification                                                    |
| ------------------------- | ------------------------------------------------------------------- | --------------------------------------------------------------- |
| create-rum-tables         | Creates 3 RUM tables (rum_page_views, rum_errors, rum_performance)  | Verify tables are created in Redshift                           |
| load-rum-data             | Uploads CSV data to S3 and loads into the 3 RUM tables              | Verify data is loaded into the RUM tables                       |

#### Additional Information About IAM Role Configuration

The IAM Role selection process is a one-time setup requirement for each AWS Root Account where the subscription exists. If you delete and later recreate the subscription in the same AWS Root Account, you will not need to reconfigure the IAM Role because:

1. The IAM configuration is cached by the service
2. The system will automatically use the previously configured IAM Role settings

**Note:** This automatic role reuse only applies when recreating subscriptions within the same AWS Root Account.

#### To deploy the module:

```
make deploy-quicksight-dataset
```

| Target                    | Result                                | Verification                                                                          |
| ------------------------- | ------------------------------------- | ------------------------------------------------------------------------------------- |
| deploy-quicksight-dataset | Deploy QuickSight datasets and dashboards | Verify the Advisor Dashboard and RUM Dashboard are created in QuickSight |

---

## 13. **Post Deployment Testing**

Open Sagemaker Lakehouse following the steps given below. 

1. Login to SageMaker Unified Studio using the Project Owner credentials (username containing "powner", e.g., `lois-lanikini-powner@example.com`)
2. Navigate to the Producer project
3. Select "Data" from the left navigation menu
4. Expand "Lakehouse" node in the second navigation menu
5. You should see "AwsDataCatalog", "s3tablescatalog", "snowflake"

Verify "financial-advisor-s3table"

1. Open "s3tablescatalog" -> "financial-advisor-s3table" -> "financial_advisor" -> "Tables"
2. You should see 24 tables: clients, advisors, accounts, portfolios, securities, transactions, holdings, market_data, performance, fees, goals, interactions, documents, compliance, research, articles, client_income_expense, client_investment_restrictions, client_reports, crawl_log, portfolio_config, recommended_products, theme_article_associations, themes
3. Click on three vertical dots next to "clients" and select "Preview data" to see first 10 records in the table
4. Repeat for other tables to verify data was loaded correctly


## 14. **Clean Up Cache**

This module helps users clean up Terraform cache from local machine. Please run the following make command to clean up local cache.

```
make clean-tf-cache
```

## Cleanup / Teardown

To tear down the solution, run the destroy commands in **reverse order** of deployment, one at a time. Wait for each command to complete before running the next. Do **NOT** use `destroy-all` as it may fail due to dependency ordering.

#### Cleanup Order

Run the following commands one at a time, in this exact order:

```
# Step 14: Clean Up Cache
make clean-tf-cache

# Step 12: QuickSight Visualization
make destroy-quicksight-dataset

# Step 11: QuickSight Subscription
make destroy-quicksight-subscription

# Step 10: Redshift Views (no destroy needed - views are dropped when Redshift is deleted)

# Step 9: Sagemaker Project Configuration
make destroy-project-config

# Step 8: Sagemaker Projects
make destroy-producer-project
make destroy-consumer-project
make destroy-project-prereq

# Step 7: Financial Advisor Data Lake
make destroy-financial-advisor-s3-glue-s3

# Step 6: Athena
make destroy-athena

# Step 5: Lake Formation (no Terraform destroy - permissions are removed when resources are deleted)

# Step 3: Sagemaker Domain
make destroy-domain
make destroy-domain-prereq

# Step 2: IAM Identity Center
make destroy-idc-acc    # or destroy-idc-org if using organization-level

# Step 1: Foundation (destroy in reverse order)
make destroy-msk
make destroy-vpc
make destroy-buckets
make destroy-iam-roles
make destroy-kms-keys

# Terraform Backend (optional - only if closing the account)
make destroy-tf-backend-cf-stack
```

#### Common Cleanup Issues

- **Security groups hanging on destroy**: Lambda VPC ENIs can take up to 20 minutes to release after the Lambda is deleted. Wait or manually detach the ENIs in the EC2 console.
- **DataZone projects stuck in DELETE_FAILED**: Use `aws datazone delete-project --domain-identifier <domain-id> --identifier <project-id> --skip-deletion-check --region <region>` to force delete.
- **DataZone domain won't delete**: Delete all projects first. If projects are stuck, force delete them with `--skip-deletion-check`, then delete the domain with `aws datazone delete-domain --identifier <domain-id> --skip-deletion-check --region <region>`.
- **S3 buckets not empty**: Empty the bucket first with `aws s3 rm s3://<bucket-name> --recursive` before running the destroy command.
- **Terraform state lock**: If a previous run was interrupted, clear the lock with `aws dynamodb delete-item --table-name <lock-table> --key '{"LockID": {"S": "<state-file-path>"}}'`.

## Troubleshooting

### IAM Policy Already Exists on Re-run

If `make deploy-iam-roles` fails with `EntityAlreadyExists` for an IAM policy, the previous run partially created the resource but Terraform state didn't record it. The make target auto-imports the policy on re-run, but if it still fails, manually import it:

```
cd iac/roots/foundation/iam-roles
terraform import -var CURRENT_ROLE="<admin-role>" aws_iam_policy.quicksight_custom_service_policy arn:aws:iam::<account-id>:policy/quicksight-access-service-policy
```

Then re-run `make deploy-iam-roles`.

### Outdated CLI version

If you encounter this error during terraform execution:

```
│ Error: local-exec provisioner error
│
│   with null_resource.create_smus_domain,
│   on domain.tf line 9, in resource "null_resource" "create_smus_domain":
│    9:   provisioner "local-exec" {
```

#### Resolution

This error may occur due to an outdated AWS CLI version. To resolve this:

1. Verify your AWS CLI version:

```
aws --version
```

2. Ensure you have AWS CLI version 2.0.0 or higher installed. Refer to the following [documentation](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) to update for Windows, macOS, and Linux.

3. After updating, retry the terraform operation

**Note**: The local-exec provisioner requires proper AWS CLI configuration to execute AWS commands successfully.

### Glue/EMR Jobs Fail: "default" Database Conflict

Certain Glue Jobs or EMR Jobs may fail if "default" Glue database exists. Please note that the "default" Glue database may also get created automatically, when you execute certain glue jobs.

#### Resolution

If you notice an error, either in a Glue job or an EMR job, related to a specific role not having permissions to "default" glue database, then please delete the "default" Glue database if it exists following the steps outlined above.

```
make grant-default-database-permissions
make drop-default-database
```
