resource "aws_security_group" "msk_client_sg" {
  name        = "${var.APP}-${var.ENV}-client-sg"
  description = "Security group for MSK EC2 Client"
  vpc_id      = local.VPC_ID

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
    Name        = "${var.APP}-${var.ENV}-client-sg"
    Environment = var.ENV
    Application = var.APP
    Usage       = "msk"
  }
}

resource "aws_instance" "msk_client" {
  ami                         = data.aws_ami.amazon_linux_2023.id
  instance_type               = "t3.large"
  subnet_id                   = local.PRIVATE_SUBNET1_ID
  vpc_security_group_ids      = [aws_security_group.msk_client_sg.id]
  iam_instance_profile        = aws_iam_instance_profile.client_instance_profile.name
  monitoring                  = true
  associate_public_ip_address = false

  metadata_options {
    http_tokens   = "required"
    http_endpoint = "enabled"
  }

  user_data = templatefile("${path.module}/user-data-topic.sh", {
    msk_cluster_ssm   = "${aws_ssm_parameter.msk_cluster_arn_primary.name}"
    source_topic_name = "intraday-source-topic"
    sink_topic_name   = "intraday-sink-topic"
    trade_topic_name  = "trade-topic"
  })

  root_block_device {
    volume_size           = 30
    volume_type           = "gp2"
    encrypted             = true
    delete_on_termination = true
  }

  tags = {
    Name = "${var.APP}-${var.ENV}-msk-client"
  }
  depends_on = [aws_msk_serverless_cluster.cluster]

  # Prevent destroy+recreate when a newer AMI is published.
  # To pick up a new AMI: terraform taint aws_instance.msk_client
  lifecycle {
    ignore_changes = [ami]
  }
}

resource "aws_iam_role" "client_instance_role" {
  name = "${var.APP}-${var.ENV}-msk-client-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_policy" "kafka_permissions" {
  name        = "${var.APP}-${var.ENV}-kafka-permissions"
  description = "Policy for MSK client Kafka permissions"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kafka-cluster:Connect",
          "kafka-cluster:DescribeCluster",
          "kafka-cluster:AlterCluster",
          "kafka-cluster:Connect",
          "kafka-cluster:AlterGroup",
          "kafka-cluster:DescribeGroup",
          "kafka-cluster:DeleteGroup",
          "kafka-cluster:*Topic*",
          "kafka-cluster:WriteData",
          "kafka-cluster:ReadData"
        ]
        Resource = [
          # Reference the cluster name from the module
          "arn:aws:kafka:${var.AWS_PRIMARY_REGION}:${data.aws_caller_identity.current.account_id}:cluster/${aws_msk_serverless_cluster.cluster.cluster_name}/*",
          "arn:aws:kafka:${var.AWS_PRIMARY_REGION}:${data.aws_caller_identity.current.account_id}:topic/${aws_msk_serverless_cluster.cluster.cluster_name}/*",
          "arn:aws:kafka:${var.AWS_PRIMARY_REGION}:${data.aws_caller_identity.current.account_id}:group/${aws_msk_serverless_cluster.cluster.cluster_name}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "ssm:DescribeParameters",
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath"
        ]
        Resource = "arn:aws:ssm:${var.AWS_PRIMARY_REGION}:${data.aws_caller_identity.current.account_id}:parameter/${var.APP}/${var.ENV}/msk/cluster_arn"
      },
      {
        Effect = "Allow"
        Action = [
          "kafka:GetBootstrapBrokers",
        ]
        Resource = "*"
      }
    ]
  })
}

# Attach the Kafka permissions policy to the role
resource "aws_iam_role_policy_attachment" "kafka_policy_attachment" {
  role       = aws_iam_role.client_instance_role.name
  policy_arn = aws_iam_policy.kafka_permissions.arn
}

# Attach SSM managed policy
resource "aws_iam_role_policy_attachment" "ssm_policy_attachment" {
  role       = aws_iam_role.client_instance_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Instance profile
resource "aws_iam_instance_profile" "client_instance_profile" {
  name = "${var.APP}-${var.ENV}-msk-client-profile"
  role = aws_iam_role.client_instance_role.name
}

data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}
