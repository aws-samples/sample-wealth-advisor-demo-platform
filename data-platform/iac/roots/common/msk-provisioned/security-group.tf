resource "aws_security_group" "provisioned_msk_primary" {
  name        = "${var.APP}-${var.ENV}-provisioned-msk-sg"
  description = "Security group for provisioned MSK cluster"
  vpc_id      = local.VPC_ID

  # Kafka broker port
  ingress {
    from_port   = 9092
    to_port     = 9092
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.vpc.cidr_block]
  }

  # TLS Kafka broker port
  ingress {
    from_port   = 9094
    to_port     = 9094
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.vpc.cidr_block]
  }

  # IAM authentication port
  ingress {
    from_port   = 9098
    to_port     = 9098
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.vpc.cidr_block]
  }

  # Zookeeper port
  ingress {
    from_port   = 2181
    to_port     = 2181
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.vpc.cidr_block]
  }

  # JMX metrics
  ingress {
    from_port   = 11001
    to_port     = 11001
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.vpc.cidr_block]
  }

  # Node exporter metrics
  ingress {
    from_port   = 11002
    to_port     = 11002
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.vpc.cidr_block]
  }

  # Allow self-referencing for inter-broker communication
  ingress {
    from_port = 0
    to_port   = 65535
    protocol  = "tcp"
    self      = true
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.APP}-${var.ENV}-provisioned-msk-sg"
    Environment = var.ENV
    Application = var.APP
    Usage       = "msk"
  }
}