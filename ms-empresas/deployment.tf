variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "project_prefix" {
  description = "Prefix for all resources"
  type        = string
  default     = "biteco"
}

variable "key_name" {
  description = "SSH key pair name"
  type        = string
  default     = "vockey"
}

locals {
  common_tags = {
    Project = var.project_prefix
  }
}

provider "aws" {
  region = var.region
}

# ---------------------------------------------------------------------------
# AMI — Ubuntu 24.04 (misma imagen que ms-usuarios)
# ---------------------------------------------------------------------------
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# ---------------------------------------------------------------------------
# Security Groups
# ---------------------------------------------------------------------------

resource "aws_security_group" "ssh" {
  name        = "${var.project_prefix}-ssh-empresas"
  description = "Allow SSH to MS-Empresas"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, { Name = "${var.project_prefix}-sg-ssh-empresas" })
}

resource "aws_security_group" "ms_empresas" {
  name        = "${var.project_prefix}-ms-empresas"
  description = "Allow HTTP traffic to MS-Empresas on port 8001"

  ingress {
    from_port   = 8001
    to_port     = 8001
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, { Name = "${var.project_prefix}-sg-ms-empresas" })
}

# Solo acepta conexiones desde la instancia EC2 de ms-empresas (aislamiento DB)
resource "aws_security_group" "rds_empresas" {
  name        = "${var.project_prefix}-rds-empresas"
  description = "Allow PostgreSQL only from MS-Empresas EC2"

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ms_empresas.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, { Name = "${var.project_prefix}-sg-rds-empresas" })
}

# ---------------------------------------------------------------------------
# RDS PostgreSQL — Base de datos aislada para ms-empresas
# ---------------------------------------------------------------------------
resource "aws_db_instance" "empresas_db" {
  identifier        = "${var.project_prefix}-empresas-db"
  engine            = "postgres"
  engine_version    = "16"
  instance_class    = "db.t3.micro"
  allocated_storage = 20
  db_name           = "empresas_db"
  username          = "postgres"
  password          = "postgres123"

  vpc_security_group_ids = [aws_security_group.rds_empresas.id]
  skip_final_snapshot    = true
  publicly_accessible    = false

  tags = merge(local.common_tags, { Name = "${var.project_prefix}-empresas-db" })
}

# ---------------------------------------------------------------------------
# EC2 — Servidor MS-Empresas
# ---------------------------------------------------------------------------
resource "aws_instance" "ms_empresas" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = "t2.medium"
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.ms_empresas.id, aws_security_group.ssh.id]
  key_name                    = var.key_name

  user_data = <<-EOT
    #!/bin/bash
    sudo apt-get update -y
    sudo apt-get install -y python3-pip python3-dev libpq-dev git

    # Variables de entorno para Django
    echo "DB_HOST=${aws_db_instance.empresas_db.address}" | sudo tee -a /etc/environment
    echo "DB_NAME=empresas_db"                            | sudo tee -a /etc/environment
    echo "DB_USER=postgres"                               | sudo tee -a /etc/environment
    echo "DB_PASSWORD=postgres123"                        | sudo tee -a /etc/environment
    echo "DB_PORT=5432"                                   | sudo tee -a /etc/environment
    echo "DJANGO_SECRET_KEY=cambiar-en-produccion"        | sudo tee -a /etc/environment

    export DB_HOST=${aws_db_instance.empresas_db.address}
    export DB_NAME=empresas_db
    export DB_USER=postgres
    export DB_PASSWORD=postgres123
    export DB_PORT=5432
    export DJANGO_SECRET_KEY=cambiar-en-produccion

    mkdir -p /labs
    cd /labs

    git clone https://github.com/gabycamps/Sprint4-Bite.co
    cd Sprint4-Bite.co/ms-empresas

    sudo pip3 install -r requirements.txt --break-system-packages --ignore-installed

    sudo -E python3 manage.py makemigrations
    sudo -E python3 manage.py migrate
    sudo -E nohup python3 manage.py runserver 0.0.0.0:8001 &
  EOT

  depends_on = [aws_db_instance.empresas_db]

  tags = merge(local.common_tags, { Name = "${var.project_prefix}-ms-empresas" })
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
output "ms_empresas_public_ip" {
  description = "IP pública del servidor MS-Empresas (para Kong)"
  value       = aws_instance.ms_empresas.public_ip
}

output "ms_empresas_private_ip" {
  description = "IP privada del servidor MS-Empresas"
  value       = aws_instance.ms_empresas.private_ip
}

output "empresas_db_host" {
  description = "Endpoint RDS de la base de datos de empresas"
  value       = aws_db_instance.empresas_db.address
}
