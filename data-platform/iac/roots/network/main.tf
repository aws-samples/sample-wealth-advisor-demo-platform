// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

provider "aws" {

  alias  = "primary"
  region = var.AWS_PRIMARY_REGION
}

provider "aws" {

  alias  = "secondary"
  region = var.AWS_SECONDARY_REGION
}

data "aws_kms_key" "primary_systems_manager_secret_key" {

  provider = aws.primary

  key_id = "alias/${var.SSM_KMS_KEY_ALIAS}"
}

data "aws_kms_key" "secondary_systems_manager_secret_key" {

  provider = aws.secondary

  key_id = "alias/${var.SSM_KMS_KEY_ALIAS}"
}

module "primary_vpc" {

  source = "../../templates/modules/vpc"
  providers = {
    aws = aws.primary
  }

  APP             = var.APP
  ENV             = var.ENV
  USAGE           = "network"
  AWS_REGION      = var.AWS_PRIMARY_REGION
  CIDR            = var.PRIMARY_CIDR
  PRIVATE_SUBNETS = var.PRIMARY_PRIVATE_SUBNETS
  PUBLIC_SUBNETS  = var.PRIMARY_PUBLIC_SUBNETS
  KMS_KEY         = data.aws_kms_key.primary_systems_manager_secret_key.arn
}

module "secondary_vpc" {

  source = "../../templates/modules/vpc"
  providers = {
    aws = aws.secondary
  }

  APP             = var.APP
  ENV             = var.ENV
  USAGE           = "network"
  AWS_REGION      = var.AWS_SECONDARY_REGION
  CIDR            = var.SECONDARY_CIDR
  PRIVATE_SUBNETS = var.SECONDARY_PRIVATE_SUBNETS
  PUBLIC_SUBNETS  = var.SECONDARY_PUBLIC_SUBNETS
  KMS_KEY         = data.aws_kms_key.secondary_systems_manager_secret_key.arn
}

module "vpc_peering" {

  source = "../../templates/modules/vpc-peering"
  providers = {
    aws.primary   = aws.primary
    aws.secondary = aws.secondary
  }

  APP                                       = var.APP
  ENV                                       = var.ENV
  USAGE                                     = "network"
  AWS_PRIMARY_REGION                        = var.AWS_PRIMARY_REGION
  AWS_SECONDARY_REGION                      = var.AWS_SECONDARY_REGION
  PRIMARY_CIDR                              = var.PRIMARY_CIDR
  SECONDARY_CIDR                            = var.SECONDARY_CIDR
  PRIMARY_VPC_ID                            = module.primary_vpc.vpc_id
  SECONDARY_VPC_ID                          = module.secondary_vpc.vpc_id
  PRIMARY_PUBLIC_SUBNET_1_ROUTE_TABLE_ID    = module.primary_vpc.public_subnet_1_route_table_id
  PRIMARY_PRIVATE_SUBNET_1_ROUTE_TABLE_ID   = module.primary_vpc.private_subnet_1_route_table_id
  PRIMARY_PRIVATE_SUBNET_2_ROUTE_TABLE_ID   = module.primary_vpc.private_subnet_2_route_table_id
  PRIMARY_PRIVATE_SUBNET_3_ROUTE_TABLE_ID   = module.primary_vpc.private_subnet_3_route_table_id
  SECONDARY_PUBLIC_SUBNET_1_ROUTE_TABLE_ID  = module.secondary_vpc.public_subnet_1_route_table_id
  SECONDARY_PRIVATE_SUBNET_1_ROUTE_TABLE_ID = module.secondary_vpc.private_subnet_1_route_table_id
  SECONDARY_PRIVATE_SUBNET_2_ROUTE_TABLE_ID = module.secondary_vpc.private_subnet_2_route_table_id
  SECONDARY_PRIVATE_SUBNET_3_ROUTE_TABLE_ID = module.secondary_vpc.private_subnet_3_route_table_id
}

module "primary_vpc_endpoint" {

  source = "../../templates/modules/vpc-endpoint"
  providers = {
    aws = aws.primary
  }

  APP             = var.APP
  ENV             = var.ENV
  USAGE           = "network"
  AWS_REGION      = var.AWS_PRIMARY_REGION
  CIDR            = var.PRIMARY_CIDR
  VPC_ID          = module.primary_vpc.vpc_id
  PUBLIC_SUBNET_1 = module.primary_vpc.public_subnets[0]
  PUBLIC_SUBNET_2 = module.primary_vpc.public_subnets[1]
  PUBLIC_SUBNET_3 = module.primary_vpc.public_subnets[2]
  SUBNET_IDS = [module.primary_vpc.public_subnet_1_route_table_id, 
                module.primary_vpc.private_subnet_1_route_table_id, 
                module.primary_vpc.private_subnet_2_route_table_id, 
                module.primary_vpc.private_subnet_3_route_table_id]
}

module "secondary_vpc_endpoint" {

  source = "../../templates/modules/vpc-endpoint"
  providers = {
    aws = aws.secondary
  }

  APP             = var.APP
  ENV             = var.ENV
  USAGE           = "network"
  AWS_REGION      = var.AWS_SECONDARY_REGION
  CIDR            = var.SECONDARY_CIDR
  VPC_ID          = module.secondary_vpc.vpc_id
  PUBLIC_SUBNET_1 = module.secondary_vpc.public_subnets[0]
  PUBLIC_SUBNET_2 = module.secondary_vpc.public_subnets[1]
  PUBLIC_SUBNET_3 = module.secondary_vpc.public_subnets[2]
  SUBNET_IDS = [module.secondary_vpc.public_subnet_1_route_table_id, 
                module.secondary_vpc.private_subnet_1_route_table_id, 
                module.secondary_vpc.private_subnet_2_route_table_id, 
                module.secondary_vpc.private_subnet_3_route_table_id]
}
