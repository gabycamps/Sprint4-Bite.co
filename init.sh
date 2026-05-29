#!/bin/bash
# init.sh — Arranque de MS-Reportes en EC2 Ubuntu 24.04
set -e

echo "=== MS-Reportes — Bite.co Sprint 4 ==="

# Instalar dependencias del sistema
sudo apt-get update -qq
sudo apt-get install -y python3-pip python3-venv postgresql-client

# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias Python
pip install --upgrade pip
pip install -r requirements.txt

# Aplicar migraciones
python manage.py migrate --noinput

# Crear superusuario si no existe (solo en desarrollo)
echo "from django.contrib.auth import get_user_model; \
U = get_user_model(); \
U.objects.filter(username='admin').exists() or \
U.objects.create_superuser('admin', 'admin@biteco.com', 'admin123')" \
| python manage.py shell || true

# Arrancar con Gunicorn (4 workers para 2 vCPU)
gunicorn ms_reportes.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 4 \
  --timeout 30 \
  --access-logfile - \
  --error-logfile - \
  --log-level info
