#!/bin/bash
# init.sh — Inicialización del microservicio ms-empresas
# Uso: bash init.sh

pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8001
