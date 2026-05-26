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

resource "aws_security_group" "ssh" {
  name        = "${var.project_prefix}-ssh"
  description = "Allow SSH"

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

  tags = merge(local.common_tags, { Name = "${var.project_prefix}-sg-ssh" })
}

resource "aws_security_group" "ms_usuarios" {
  name        = "${var.project_prefix}-ms-usuarios"
  description = "Allow traffic to MS-Usuarios"

  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, { Name = "${var.project_prefix}-sg-ms-usuarios" })
}

resource "aws_security_group" "rds_usuarios" {
  name        = "${var.project_prefix}-rds-usuarios"
  description = "Allow PostgreSQL from MS-Usuarios"

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ms_usuarios.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, { Name = "${var.project_prefix}-sg-rds-usuarios" })
}

resource "aws_db_instance" "usuarios_db" {
  identifier        = "${var.project_prefix}-usuarios-db"
  engine            = "postgres"
  engine_version    = "16"
  instance_class    = "db.t3.micro"
  allocated_storage = 20
  db_name           = "usuarios_db"
  username          = "postgres"
  password          = "postgres123"
  
  vpc_security_group_ids = [aws_security_group.rds_usuarios.id]
  skip_final_snapshot    = true
  publicly_accessible    = false

  tags = merge(local.common_tags, { Name = "${var.project_prefix}-usuarios-db" })
}

resource "aws_instance" "ms_usuarios" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = "t2.medium"
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.ms_usuarios.id, aws_security_group.ssh.id]
  key_name                    = var.key_name

 user_data = <<-EOT
    #!/bin/bash
    sudo apt-get update -y
    sudo apt-get install -y python3-pip python3-dev libpq-dev git

    echo "DB_HOST=${aws_db_instance.usuarios_db.address}" | sudo tee -a /etc/environment
    echo "DB_NAME=usuarios_db" | sudo tee -a /etc/environment
    echo "DB_USER=postgres" | sudo tee -a /etc/environment
    echo "DB_PASSWORD=postgres123" | sudo tee -a /etc/environment
    echo "DB_PORT=5432" | sudo tee -a /etc/environment

    export DB_HOST=${aws_db_instance.usuarios_db.address}
    export DB_NAME=usuarios_db
    export DB_USER=postgres
    export DB_PASSWORD=postgres123
    export DB_PORT=5432

    mkdir -p /labs
    cd /labs

    git clone https://github.com/gabycamps/Sprint4-Bite.co
    cd Sprint4-Bite.co/ms-usuarios

    sudo pip3 install -r requirements.txt --break-system-packages

    sudo -E python3 manage.py makemigrations
    sudo -E python3 manage.py migrate
    sudo -E nohup python3 manage.py runserver 0.0.0.0:8000 &
  EOT

  depends_on = [aws_db_instance.usuarios_db]

  tags = merge(local.common_tags, { Name = "${var.project_prefix}-ms-usuarios" })
}

output "ms_usuarios_public_ip" {
  value = aws_instance.ms_usuarios.public_ip
}

output "ms_usuarios_private_ip" {
  value = aws_instance.ms_usuarios.private_ip
}

output "usuarios_db_host" {
  value = aws_db_instance.usuarios_db.address
}
