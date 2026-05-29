###############################################################################
# deployment.tf — MS-Reportes  |  Bite.co Sprint 4
# EC2 Ubuntu 24.04 | 2 vCPU | 8 GB RAM
# Región: us-east-1 (igual que los otros microservicios)
###############################################################################

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

# ---------------------------------------------------------------------------
# Variables
# ---------------------------------------------------------------------------
variable "key_name" {
  description = "Nombre del key pair para acceso SSH"
  type        = string
  default     = "biteco-key"
}

variable "django_secret_key" {
  description = "SECRET_KEY de Django (no commitear en producción)"
  type        = string
  sensitive   = true
  default     = "clave-local-development-no-usar-en-prod"
}

variable "db_password" {
  description = "Contraseña de PostgreSQL para reportes_db"
  type        = string
  sensitive   = true
  default     = "postgres"
}

variable "ms_empresas_url" {
  description = "URL interna del MS-Empresas"
  type        = string
  default     = "http://172.31.84.93:8001"  # IP privada biteco-ms-empresas
}

variable "ms_consumos_url" {
  description = "URL interna del MS-Consumos"
  type        = string
  default     = "http://172.31.89.179:8002"  # IP privada biteco-ms-consumos
}

variable "redis_url" {
  description = "URL del servidor Redis"
  type        = string
  default     = "redis://localhost:6379/0"
}

# ---------------------------------------------------------------------------
# Security Group — permite HTTP 8000, SSH 22, PostgreSQL 5432
# ---------------------------------------------------------------------------
resource "aws_security_group" "biteco_ms_reportes" {
  name        = "biteco-ms-reportes-sg"
  description = "Security group para MS-Reportes Bite.co"

  ingress {
    description = "HTTP MS-Reportes"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "PostgreSQL"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["172.31.0.0/16"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name    = "biteco-ms-reportes-sg"
    Proyecto = "biteco-sprint4"
  }
}

# ---------------------------------------------------------------------------
# AMI — Ubuntu 24.04 LTS us-east-1
# ---------------------------------------------------------------------------
data "aws_ami" "ubuntu_24" {
  most_recent = true
  owners      = ["099720109477"]  # Canonical

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
# EC2 Instance — MS-Reportes
# ---------------------------------------------------------------------------
resource "aws_instance" "ms_reportes" {
  ami                    = data.aws_ami.ubuntu_24.id
  instance_type          = "t3.large"   # 2 vCPU, 8 GB RAM
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.biteco_ms_reportes.id]

  user_data = templatefile("${path.module}/init.sh", {})

  # Variables de entorno para el servicio
  user_data = <<-EOF
    #!/bin/bash
    set -e

    # Variables de entorno
    export DJANGO_SECRET_KEY="${var.django_secret_key}"
    export DB_NAME="reportes_db"
    export DB_USER="postgres"
    export DB_PASSWORD="${var.db_password}"
    export DB_HOST="localhost"
    export DB_PORT="5432"
    export MS_EMPRESAS_URL="${var.ms_empresas_url}"
    export MS_CONSUMOS_URL="${var.ms_consumos_url}"
    export REDIS_URL="${var.redis_url}"
    export CACHE_TTL_SEGUNDOS="300"

    # Persistir en /etc/environment para que estén disponibles en sesiones SSH
    echo "DJANGO_SECRET_KEY=${var.django_secret_key}" >> /etc/environment
    echo "DB_NAME=reportes_db" >> /etc/environment
    echo "DB_USER=postgres" >> /etc/environment
    echo "DB_PASSWORD=${var.db_password}" >> /etc/environment
    echo "DB_HOST=localhost" >> /etc/environment
    echo "DB_PORT=5432" >> /etc/environment
    echo "MS_EMPRESAS_URL=${var.ms_empresas_url}" >> /etc/environment
    echo "MS_CONSUMOS_URL=${var.ms_consumos_url}" >> /etc/environment
    echo "REDIS_URL=${var.redis_url}" >> /etc/environment
    echo "CACHE_TTL_SEGUNDOS=300" >> /etc/environment

    # Instalar PostgreSQL y Python
    apt-get update -qq
    apt-get install -y python3-pip python3-venv postgresql postgresql-contrib

    # Crear base de datos
    sudo -u postgres psql -c "CREATE DATABASE reportes_db;" || true
    sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD '${var.db_password}';" || true

    # Clonar o copiar el servicio (ajustar URL del repo)
    cd /home/ubuntu
    git clone https://github.com/gabycamps/Sprint4-Bite.co.git || true

    # Instalar ms-reportes
    cd /home/ubuntu/ms-reportes
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    python manage.py migrate --noinput

    # Arrancar con gunicorn como servicio systemd
    cat > /etc/systemd/system/ms-reportes.service <<SERVICE
    [Unit]
    Description=MS-Reportes Bite.co
    After=network.target

    [Service]
    User=ubuntu
    WorkingDirectory=/home/ubuntu/ms-reportes
    EnvironmentFile=/etc/environment
    ExecStart=/home/ubuntu/ms-reportes/venv/bin/gunicorn ms_reportes.wsgi:application --bind 0.0.0.0:8000 --workers 4 --timeout 30
    Restart=always

    [Install]
    WantedBy=multi-user.target
    SERVICE

    systemctl daemon-reload
    systemctl enable ms-reportes
    systemctl start ms-reportes
  EOF

  tags = {
    Name     = "biteco-ms-reportes"
    Proyecto = "biteco-sprint4"
  }
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
output "ms_reportes_public_ip" {
  value       = aws_instance.ms_reportes.public_ip
  description = "IP pública de MS-Reportes"
}

output "ms_reportes_private_ip" {
  value       = aws_instance.ms_reportes.private_ip
  description = "IP privada de MS-Reportes (para Kong y otros MS)"
}
