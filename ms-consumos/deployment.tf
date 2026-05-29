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
# AMI — Ubuntu 24.04 (misma que ms-usuarios y ms-empresas)
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
resource "aws_security_group" "ssh_consumos" {
  name        = "${var.project_prefix}-ssh-consumos"
  description = "Allow SSH to MS-Consumos"

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

  tags = merge(local.common_tags, { Name = "${var.project_prefix}-sg-ssh-consumos" })
}

resource "aws_security_group" "ms_consumos" {
  name        = "${var.project_prefix}-ms-consumos"
  description = "Allow HTTP traffic to MS-Consumos on port 8002"

  ingress {
    from_port   = 8002
    to_port     = 8002
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, { Name = "${var.project_prefix}-sg-ms-consumos" })
}

# ---------------------------------------------------------------------------
# EC2 — Servidor MS-Consumos (FastAPI + MongoDB en Docker)
# ---------------------------------------------------------------------------
resource "aws_instance" "ms_consumos" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = "t2.medium"
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.ms_consumos.id, aws_security_group.ssh_consumos.id]
  key_name                    = var.key_name

  user_data = <<-EOT
    #!/bin/bash
    sudo apt-get update -y
    sudo apt-get install -y python3-pip python3-venv python3-dev git

    # Instalar Docker para correr MongoDB como contenedor
    sudo apt-get install -y ca-certificates curl
    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io

    # Correr MongoDB como contenedor Docker en la misma EC2
    sudo docker run -d -p 27017:27017 --name mongodb --restart always mongo:6.0

    # Variable de entorno para que FastAPI sepa dónde está MongoDB
    echo "MONGO_URL=mongodb://localhost:27017" | sudo tee -a /etc/environment
    export MONGO_URL=mongodb://localhost:27017

    # Clonar el repo y correr el microservicio
    mkdir -p /labs
    cd /labs
    git clone https://github.com/gabycamps/Sprint4-Bite.co.git
    cd Sprint4-Bite.co/ms-consumos

    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt

    nohup venv/bin/python main.py > app.log 2>&1 &
  EOT

  tags = merge(local.common_tags, { Name = "${var.project_prefix}-ms-consumos" })
}

# ---------------------------------------------------------------------------
# Outputs — IPs para configurar Kong después
# ---------------------------------------------------------------------------
output "ms_consumos_public_ip" {
  description = "IP pública del servidor MS-Consumos (para Kong)"
  value       = aws_instance.ms_consumos.public_ip
}

output "ms_consumos_private_ip" {
  description = "IP privada del servidor MS-Consumos"
  value       = aws_instance.ms_consumos.private_ip
}