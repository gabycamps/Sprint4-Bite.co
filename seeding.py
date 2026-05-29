"""
seeding.py — Datos de prueba para RecursoCloud
Experimento ASR Mantenibilidad: genera registros para que
calcular_costo_instancias_bajo_demanda tenga datos reales sobre qué operar.

Uso:
  python manage.py shell < seeding.py
  o: python seeding.py (con DJANGO_SETTINGS_MODULE configurado)
"""

import os
import sys
import random
from datetime import date, timedelta
from decimal import Decimal

# Configuración Django si se ejecuta standalone
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ms_reportes.settings')

import django
django.setup()

from reportes.models import RecursoCloud

TIPOS_INSTANCIA = [
    't2.micro', 't2.small', 't2.medium',
    't3.micro', 't3.small', 't3.medium',
    'm5.large',
]

PROYECTOS = [f'proyecto-{i}' for i in range(1, 11)]


def generar_recursos(n_por_proyecto: int = 30):
    """
    Genera n_por_proyecto registros de RecursoCloud para cada proyecto.
    Total: 10 proyectos × 30 registros = 300 recursos cloud.
    """
    print(f"Generando recursos cloud — {len(PROYECTOS)} proyectos × {n_por_proyecto} registros...")
    creados = 0

    for proyecto_id in PROYECTOS:
        fecha_base = date(2025, 1, 1)
        for i in range(n_por_proyecto):
            fecha = fecha_base + timedelta(days=random.randint(0, 364))
            RecursoCloud.objects.get_or_create(
                proyecto_id=proyecto_id,
                tipo_instancia=random.choice(TIPOS_INSTANCIA),
                fecha_registro=fecha,
                defaults={
                    'cantidad': random.randint(1, 5),
                    'horas_uso': Decimal(str(round(random.uniform(10, 720), 2))),
                    'activo': True,
                }
            )
            creados += 1

    print(f"✓ {creados} recursos cloud generados.")


if __name__ == '__main__':
    generar_recursos()
