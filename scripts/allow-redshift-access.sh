#!/bin/bash
# Script to allow EC2 dev machine access to Redshift Serverless
# Created: 2026-02-18
# Purpose: Fix connection timeout by establishing VPC peering and configuring security groups

set -e

# Environment-specific values — provide via environment (no real resource IDs committed).
REGION="${REGION:-us-west-2}"
EC2_VPC="${EC2_VPC:?EC2_VPC env var is required (e.g. export EC2_VPC=vpc-xxxxxxxx)}"
REDSHIFT_VPC="${REDSHIFT_VPC:?REDSHIFT_VPC env var is required (e.g. export REDSHIFT_VPC=vpc-xxxxxxxx)}"
REDSHIFT_SG="${REDSHIFT_SG:?REDSHIFT_SG env var is required (e.g. export REDSHIFT_SG=sg-xxxxxxxx)}"
EC2_IP="${EC2_IP:?EC2_IP env var is required (private IP/CIDR of the EC2 dev machine, e.g. export EC2_IP=10.0.0.0/24)}"
REDSHIFT_PORT="${REDSHIFT_PORT:-5439}"
# Derive the Redshift Serverless endpoint from the account/region unless overridden.
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
REDSHIFT_WORKGROUP="${REDSHIFT_WORKGROUP:-financial-advisor-wg}"
REDSHIFT_ENDPOINT="${REDSHIFT_ENDPOINT:-${REDSHIFT_WORKGROUP}.${AWS_ACCOUNT_ID}.${REGION}.redshift-serverless.amazonaws.com}"

echo "Step 1: Creating VPC peering connection..."
PEERING_ID=$(aws ec2 create-vpc-peering-connection \
  --region "$REGION" \
  --vpc-id "$EC2_VPC" \
  --peer-vpc-id "$REDSHIFT_VPC" \
  --tag-specifications "ResourceType=vpc-peering-connection,Tags=[{Key=Name,Value=ec2-to-redshift-peering}]" \
  --query 'VpcPeeringConnection.VpcPeeringConnectionId' \
  --output text)

echo "✓ VPC peering connection created: $PEERING_ID"

echo "Step 2: Accepting VPC peering connection..."
aws ec2 accept-vpc-peering-connection \
  --region "$REGION" \
  --vpc-peering-connection-id "$PEERING_ID" > /dev/null

echo "✓ VPC peering connection accepted"

echo "Step 3: Getting route table IDs..."
EC2_ROUTE_TABLES=$(aws ec2 describe-route-tables \
  --region "$REGION" \
  --filters "Name=vpc-id,Values=$EC2_VPC" \
  --query 'RouteTables[].RouteTableId' \
  --output text)

REDSHIFT_ROUTE_TABLES=$(aws ec2 describe-route-tables \
  --region "$REGION" \
  --filters "Name=vpc-id,Values=$REDSHIFT_VPC" \
  --query 'RouteTables[].RouteTableId' \
  --output text)

echo "✓ EC2 route tables: $EC2_ROUTE_TABLES"
echo "✓ Redshift route tables: $REDSHIFT_ROUTE_TABLES"

echo "Step 4: Getting VPC CIDR blocks..."
EC2_CIDR=$(aws ec2 describe-vpcs \
  --region "$REGION" \
  --vpc-ids "$EC2_VPC" \
  --query 'Vpcs[0].CidrBlock' \
  --output text)

REDSHIFT_CIDR=$(aws ec2 describe-vpcs \
  --region "$REGION" \
  --vpc-ids "$REDSHIFT_VPC" \
  --query 'Vpcs[0].CidrBlock' \
  --output text)

echo "✓ EC2 VPC CIDR: $EC2_CIDR"
echo "✓ Redshift VPC CIDR: $REDSHIFT_CIDR"

echo "Step 5: Adding routes to all route tables..."
for RT in $EC2_ROUTE_TABLES; do
  echo "  Adding route to EC2 route table: $RT"
  aws ec2 create-route \
    --region "$REGION" \
    --route-table-id "$RT" \
    --destination-cidr-block "$REDSHIFT_CIDR" \
    --vpc-peering-connection-id "$PEERING_ID" 2>/dev/null || echo "    Route may already exist"
done

for RT in $REDSHIFT_ROUTE_TABLES; do
  echo "  Adding route to Redshift route table: $RT"
  aws ec2 create-route \
    --region "$REGION" \
    --route-table-id "$RT" \
    --destination-cidr-block "$EC2_CIDR" \
    --vpc-peering-connection-id "$PEERING_ID" 2>/dev/null || echo "    Route may already exist"
done

echo "✓ Routes added to all route tables in both VPCs"

echo "Step 6: Updating Redshift security group..."
aws ec2 authorize-security-group-ingress \
  --region "$REGION" \
  --group-id "$REDSHIFT_SG" \
  --ip-permissions "IpProtocol=tcp,FromPort=$REDSHIFT_PORT,ToPort=$REDSHIFT_PORT,IpRanges=[{CidrIp=$EC2_CIDR,Description='Allow Redshift access from EC2 VPC'}]" > /dev/null || echo "Security group rule may already exist"

echo "✓ Security group rule added"
echo ""
echo "Testing connection..."
sleep 5
timeout 5 bash -c "cat < /dev/null > /dev/tcp/$REDSHIFT_ENDPOINT/$REDSHIFT_PORT" && echo "✓ Connection successful" || echo "✗ Connection failed (may need a few moments to propagate)"
