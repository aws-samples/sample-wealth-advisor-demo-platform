#!/bin/bash

set -e

# Configuration
VPC_ID="vpc-0a9c92e6fe62049c1"
REGION="us-west-2"
SUBNET_1_CIDR="172.31.64.0/20"
SUBNET_1_AZ="us-west-2b"
SUBNET_1_NAME="wealth-mgmt-private-1"
SUBNET_2_CIDR="172.31.80.0/20"
SUBNET_2_AZ="us-west-2a"
SUBNET_2_NAME="wealth-mgmt-private-2"

echo "Setting up private subnets in VPC: $VPC_ID"

# Check if subnets already exist
EXISTING_SUBNET_1=$(aws ec2 describe-subnets --region $REGION --filters "Name=vpc-id,Values=$VPC_ID" "Name=cidr-block,Values=$SUBNET_1_CIDR" --query 'Subnets[0].SubnetId' --output text 2>/dev/null || echo "None")
EXISTING_SUBNET_2=$(aws ec2 describe-subnets --region $REGION --filters "Name=vpc-id,Values=$VPC_ID" "Name=cidr-block,Values=$SUBNET_2_CIDR" --query 'Subnets[0].SubnetId' --output text 2>/dev/null || echo "None")

if [[ "$EXISTING_SUBNET_1" != "None" && "$EXISTING_SUBNET_1" != "null" ]]; then
    echo "Private subnet 1 already exists: $EXISTING_SUBNET_1"
    SUBNET_1_ID="$EXISTING_SUBNET_1"
else
    echo "Creating private subnet 1: $SUBNET_1_CIDR in $SUBNET_1_AZ"
    SUBNET_1_ID=$(aws ec2 create-subnet --region $REGION --vpc-id $VPC_ID --cidr-block $SUBNET_1_CIDR --availability-zone $SUBNET_1_AZ --query 'Subnet.SubnetId' --output text)
    aws ec2 create-tags --region $REGION --resources $SUBNET_1_ID --tags Key=Name,Value=$SUBNET_1_NAME Key=Type,Value=Private
    echo "Created subnet 1: $SUBNET_1_ID"
fi

if [[ "$EXISTING_SUBNET_2" != "None" && "$EXISTING_SUBNET_2" != "null" ]]; then
    echo "Private subnet 2 already exists: $EXISTING_SUBNET_2"
    SUBNET_2_ID="$EXISTING_SUBNET_2"
else
    echo "Creating private subnet 2: $SUBNET_2_CIDR in $SUBNET_2_AZ"
    SUBNET_2_ID=$(aws ec2 create-subnet --region $REGION --vpc-id $VPC_ID --cidr-block $SUBNET_2_CIDR --availability-zone $SUBNET_2_AZ --query 'Subnet.SubnetId' --output text)
    aws ec2 create-tags --region $REGION --resources $SUBNET_2_ID --tags Key=Name,Value=$SUBNET_2_NAME Key=Type,Value=Private
    echo "Created subnet 2: $SUBNET_2_ID"
fi

# Check if route table already exists
EXISTING_RT=$(aws ec2 describe-route-tables --region $REGION --filters "Name=vpc-id,Values=$VPC_ID" "Name=tag:Name,Values=wealth-mgmt-private-rt" --query 'RouteTables[0].RouteTableId' --output text 2>/dev/null || echo "None")

if [[ "$EXISTING_RT" != "None" && "$EXISTING_RT" != "null" ]]; then
    echo "Private route table already exists: $EXISTING_RT"
    RT_ID="$EXISTING_RT"
else
    echo "Creating private route table"
    RT_ID=$(aws ec2 create-route-table --region $REGION --vpc-id $VPC_ID --query 'RouteTable.RouteTableId' --output text)
    aws ec2 create-tags --region $REGION --resources $RT_ID --tags Key=Name,Value=wealth-mgmt-private-rt
    echo "Created route table: $RT_ID"
fi

# Associate subnets with route table (idempotent)
echo "Associating subnets with route table"
aws ec2 associate-route-table --region $REGION --subnet-id $SUBNET_1_ID --route-table-id $RT_ID 2>/dev/null || echo "Subnet 1 already associated"
aws ec2 associate-route-table --region $REGION --subnet-id $SUBNET_2_ID --route-table-id $RT_ID 2>/dev/null || echo "Subnet 2 already associated"

echo "Setup complete!"
echo "Subnet IDs for Task 2:"
echo "  $SUBNET_1_ID"
echo "  $SUBNET_2_ID"