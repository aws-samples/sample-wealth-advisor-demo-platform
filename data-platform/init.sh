#!/usr/bin/env bash

# Copyright 2025 Amazon.com and its affiliates; all rights reserved.
# SPDX-License-Identifier: LicenseRef-.amazon.com.-AmznSL-1.0
# Licensed under the Amazon Software License  https://aws.amazon.com/asl/

# Reads a .template file, resolves ###PLACEHOLDER### tokens with environment
# variable values, and writes the result to the corresponding output file
# (template path minus the .template suffix).
# param1: path to the .template file
resolve_template () {

    local templatePath="$1"
    local outputPath="${templatePath%.template}"

    local SED_PATTERNS
    local resolvedContent="$(cat "$templatePath")"

    # Replace each ###VAR### placeholder with its value
    local varName
    while read varName
    do
        local envVarValue="${!varName}"

        if [[ "$envVarValue" == "blank" ]]; then
            envVarValue=""
        fi

        SED_PATTERNS="s|###${varName}###|${envVarValue}|g;"

        resolvedContent="$(echo "$resolvedContent" | sed ''"$SED_PATTERNS"'')"

    done <<< "$(IFS=$'\n'; echo -e "${ENV_KEYS[*]}" )"

    echo "$resolvedContent" > "$outputPath"
}

# Validates that a name is safe for S3 bucket naming and AWS resource names.
# Rules: lowercase alphanumeric only, 1-6 characters.
# param1: the value to validate
# param2: the field name (for error messages)
validate_name () {
    local value="$1"
    local field="$2"

    if [[ -z "$value" ]]; then
        echo "  ERROR: ${field} cannot be empty."
        return 1
    fi

    if [[ ${#value} -gt 6 ]]; then
        echo "  ERROR: ${field} must be 6 characters or fewer (got ${#value})."
        return 1
    fi

    if [[ ! "$value" =~ ^[a-z0-9]+$ ]]; then
        echo "  ERROR: ${field} must contain only lowercase letters and numbers."
        echo "         No uppercase, underscores, hyphens, or special characters."
        echo "         S3 bucket names are derived from this value and have strict naming rules."
        return 1
    fi

    return 0
}

echo -e "\nGreetings prototype user! Before you can get started deploying this prototype,"
echo -e "we need to collect some settings values from you...\n"

echo -e "\n12 digit AWS account ID to deploy resources to"
read -p "Enter value: " answer
AWS_ACCOUNT_ID="$answer"

echo -e "\nThe application name that is used to name resources (including S3 buckets).
Rules: lowercase letters and numbers only, max 6 characters.
Example: daivi"
while true; do
    read -p "Enter value: " answer
    if validate_name "$answer" "APP_NAME"; then
        break
    fi
done
APP_NAME="$answer"

echo -e "\nThe environment name that is used to name resources and to determine
the value of environment-specific configurations.
Rules: lowercase letters and numbers only, max 6 characters.
Examples: quid7, mxr9, your initials with a number"
while true; do
    read -p "Enter value: " answer
    if validate_name "$answer" "ENV_NAME"; then
        break
    fi
done
ENV_NAME="$answer"

echo -e "\nPrimary AWS region to deploy application resources to
Example: us-east-1"
read -p "Enter value: " answer
AWS_PRIMARY_REGION="$answer"
AWS_DEFAULT_REGION="$answer"

echo -e "\nSecondary AWS region to deploy application resources to
Example: us-west-2"
read -p "Enter value: " answer
AWS_SECONDARY_REGION="$answer"

echo -e "\nThe name of an existing IAM role to be granted Lake Formation admin access.
This role must already exist in your account before proceeding.
If you don't have one, create it first:
  aws iam create-role --role-name Admin --assume-role-policy-document '{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Principal\":{\"AWS\":\"arn:aws:iam::'"\$AWS_ACCOUNT_ID"':root\"},\"Action\":\"sts:AssumeRole\"}]}'
  aws iam attach-role-policy --role-name Admin --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
Example: Admin"
read -p "Enter value: " answer
ADMIN_ROLE="$answer"

TF_S3_BACKEND_NAME="${APP_NAME}-${ENV_NAME}-tf-back-end"

envKeysString="AWS_ACCOUNT_ID APP_NAME AWS_DEFAULT_REGION ENV_NAME AWS_PRIMARY_REGION AWS_SECONDARY_REGION TF_S3_BACKEND_NAME ADMIN_ROLE"
ENV_KEYS=($(echo "$envKeysString"))

# List of .template files to resolve. Each entry is the path to the generated
# output file — the script appends .template to find the source.
templateFilePathsStr="./set-env-vars.sh ./Makefile
./iac/roots/quicksight/dataset/terraform.tfvars
./iac/roots/quicksight/dataset/backend.tf
./iac/roots/quicksight/subscription/terraform.tfvars
./iac/roots/quicksight/subscription/backend.tf
./iac/roots/idc/idc-org/terraform.tfvars
./iac/roots/idc/idc-org/backend.tf
./iac/roots/idc/idc-acc/terraform.tfvars
./iac/roots/idc/idc-acc/backend.tf
./iac/roots/idc/disable-mfa/terraform.tfvars
./iac/roots/spark-code-interpreter/terraform.tfvars
./iac/roots/spark-code-interpreter/backend.tf
./iac/roots/network/terraform.tfvars
./iac/roots/network/backend.tf
./iac/roots/foundation/buckets/terraform.tfvars
./iac/roots/foundation/buckets/backend.tf
./iac/roots/foundation/iam-roles/terraform.tfvars
./iac/roots/foundation/iam-roles/backend.tf
./iac/roots/foundation/msk-serverless/terraform.tfvars
./iac/roots/foundation/msk-serverless/backend.tf
./iac/roots/foundation/vpc/terraform.tfvars
./iac/roots/foundation/vpc/backend.tf
./iac/roots/foundation/kms-keys/terraform.tfvars
./iac/roots/foundation/kms-keys/backend.tf
./iac/roots/common/msk-provisioned/terraform.tfvars
./iac/roots/common/msk-provisioned/backend.tf
./iac/roots/datazone/dz-project-prereq/terraform.tfvars
./iac/roots/datazone/dz-project-prereq/backend.tf
./iac/roots/datazone/dz-custom-project/terraform.tfvars
./iac/roots/datazone/dz-custom-project/backend.tf
./iac/roots/datazone/dz-domain/terraform.tfvars
./iac/roots/datazone/dz-domain/backend.tf
./iac/roots/datazone/data-assets-glossary/terraform.tfvars
./iac/roots/datazone/data-assets-glossary/backend.tf
./iac/roots/datazone/dz-consumer-project/terraform.tfvars
./iac/roots/datazone/dz-consumer-project/backend.tf
./iac/roots/datazone/dz-producer-project/terraform.tfvars
./iac/roots/datazone/dz-producer-project/backend.tf
./iac/roots/sagemaker/consumer-project/terraform.tfvars
./iac/roots/sagemaker/consumer-project/backend.tf
./iac/roots/sagemaker/producer-project/terraform.tfvars
./iac/roots/sagemaker/producer-project/backend.tf
./iac/roots/sagemaker/snowflake-connection/terraform.tfvars
./iac/roots/sagemaker/snowflake-connection/backend.tf
./iac/roots/sagemaker/domain-prereq/terraform.tfvars
./iac/roots/sagemaker/domain-prereq/backend.tf
./iac/roots/sagemaker/project-config/terraform.tfvars
./iac/roots/sagemaker/project-config/backend.tf
./iac/roots/sagemaker/project-user/terraform.tfvars
./iac/roots/sagemaker/project-user/backend.tf
./iac/roots/sagemaker/domain/terraform.tfvars
./iac/roots/sagemaker/domain/backend.tf
./iac/roots/sagemaker/project-prereq/terraform.tfvars
./iac/roots/sagemaker/project-prereq/backend.tf
./iac/roots/athena/terraform.tfvars
./iac/roots/athena/backend.tf
./iac/roots/datalakes/financial-advisor-s3-glue-s3/terraform.tfvars
./iac/roots/datalakes/financial-advisor-s3-glue-s3/backend.tf
./iac/bootstrap/parameters.json
./iac/bootstrap/parameters-secondary.json
./iac/bootstrap/parameters-crr.json
./review/checkov.txt"
templateFilePaths=($(echo "$templateFilePathsStr"))

for outputPath in "${templateFilePaths[@]}"; do

    templatePath="${outputPath}.template"

    if [[ -f "$templatePath" ]]; then
        echo -e "\nGenerating ${outputPath} from ${templatePath}"
        resolve_template "$templatePath"
    fi
done

echo -e "\nSUCCESS!"
echo -e "To re-run with different values, just run 'make init' again.\n"
