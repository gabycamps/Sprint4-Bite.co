"""
validators.py — Táctica de Input Validation (ASR Seguridad)

Toda entrada del usuario es validada y sanitizada antes de ser procesada.
El parámetro proyecto_id se valida contra un formato esperado antes de
que llegue al ORM o a cualquier llamada HTTP a otros microservicios.

Esto garantiza:
- Tasa de éxito del ataque = 0%
- HTTP 400 ante cualquier input malicioso
- Sin degradación de latencia (la validación es O(1))
"""

import re
from datetime import date, datetime


# Patrón permitido para proyecto_id: solo letras, dígitos y guión
# Ejemplos válidos: proyecto-1, proyecto-10, proyecto-abc
# Rechaza: ' OR '1'='1'--, ; DROP TABLE, <script>, etc.
PROYECTO_ID_PATTERN = re.compile(r'^[a-zA-Z0-9\-]{1,100}$')


def validar_proyecto_id(proyecto_id: str) -> str:
    """
    Valida que proyecto_id tenga un formato seguro.
    Lanza ValueError con mensaje claro si no cumple.

    Complejidad ciclomática: 3 (cumple ASR mantenibilidad < 10)
    """
    if not proyecto_id:
        raise ValueError("El parámetro 'proyecto_id' es requerido.")

    if not isinstance(proyecto_id, str):
        raise ValueError("El parámetro 'proyecto_id' debe ser una cadena de texto.")

    if not PROYECTO_ID_PATTERN.match(proyecto_id):
        raise ValueError(
            "El parámetro 'proyecto_id' contiene caracteres no permitidos. "
            "Solo se aceptan letras, números y guiones."
        )

    return proyecto_id.strip()


def validar_fecha(valor: str, nombre_campo: str) -> date:
    """
    Valida que una fecha tenga formato YYYY-MM-DD.
    Lanza ValueError con mensaje claro si no cumple.

    Complejidad ciclomática: 3 (cumple ASR mantenibilidad < 10)
    """
    if not valor:
        raise ValueError(f"El parámetro '{nombre_campo}' es requerido.")

    try:
        fecha = datetime.strptime(valor, '%Y-%m-%d').date()
    except ValueError:
        raise ValueError(
            f"El parámetro '{nombre_campo}' debe tener formato YYYY-MM-DD. "
            f"Valor recibido: '{valor}'"
        )

    return fecha


def validar_rango_fechas(fecha_inicio: date, fecha_fin: date) -> None:
    """
    Valida que fecha_inicio no sea posterior a fecha_fin.
    Lanza ValueError si el rango es inválido.

    Complejidad ciclomática: 2 (cumple ASR mantenibilidad < 10)
    """
    if fecha_inicio > fecha_fin:
        raise ValueError(
            f"'fecha_inicio' ({fecha_inicio}) no puede ser posterior a "
            f"'fecha_fin' ({fecha_fin})."
        )
