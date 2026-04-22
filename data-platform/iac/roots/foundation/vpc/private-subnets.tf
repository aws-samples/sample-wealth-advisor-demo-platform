// Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

resource "aws_subnet" "private" {

  # Create at least 3 private subnets in different AZs or at most 4
  count             = local.max_az_count
  vpc_id            = aws_vpc.main.id
  # Following the CIDR scheme provisioned by the console namely, 10.38.192.0/21, 10.38.200.0/21, 10.28.208.0/21, and 10.38.216.0/21
  cidr_block        = "10.38.${count.index * 8 + 192}.0/21"
  availability_zone = data.aws_availability_zones.available.names[count.index]
  tags = {
    Name = "${var.APP}-${var.ENV}-private-subnet-${count.index + 1}"
    Application = var.APP
    Environment = var.ENV
  }
}

# Elastic IP for NAT Gateway
resource "aws_eip" "nat" {

  domain = "vpc"

  tags = {
    Name = "${var.APP}-${var.ENV}-nat-eip"
    Application = var.APP
    Environment = var.ENV
  }
}

# NAT Gateway
resource "aws_nat_gateway" "main" {

  allocation_id = aws_eip.nat.allocation_id
  subnet_id     = aws_subnet.public[0].id

  tags = {
    Name = "${var.APP}-${var.ENV}-nat-gateway"
    Application = var.APP
    Environment = var.ENV
  }

  depends_on = [aws_internet_gateway.main]
}

# Route table for private subnets
resource "aws_route_table" "private" {

  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main.id
  }

  tags = {
    Name = "${var.APP}-${var.ENV}-private-rt"
    Application = var.APP
    Environment = var.ENV
  }
}

# Associate private subnets with private route table
resource "aws_route_table_association" "private" {

  count          = local.max_az_count
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

# Save the Subnet Ids in SSM Parameter Store
resource "aws_ssm_parameter" "private_subnet_ids" {

  name      = "/${var.APP}/${var.ENV}/vpc_private_subnet_ids"
  type      = "SecureString"
  value     = join(",", aws_subnet.private[*].id)
  key_id    = data.aws_kms_key.ssm_kms_key.key_id
  overwrite = true

  tags = {
    Application = var.APP
    Environment = var.ENV
  }
}

resource "aws_ssm_parameter" "availability_zone_names" {
  
  name      = "/${var.APP}/${var.ENV}/vpc_availability_zone_names"
  type      = "SecureString"
  value     = join(",", aws_subnet.private[*].availability_zone)
  key_id    = data.aws_kms_key.ssm_kms_key.key_id
  overwrite = true

  tags = {
    Application = var.APP
    Environment = var.ENV
  }
}

resource "aws_ssm_parameter" "private_route_table_id" {
  name      = "/${var.APP}/${var.ENV}/vpc_private_route_table_id"
  type      = "SecureString"
  value     = aws_route_table.private.id
  key_id    = data.aws_kms_key.ssm_kms_key.key_id
  overwrite = true

  tags = {
    Application = var.APP
    Environment = var.ENV
  }
}
