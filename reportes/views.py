"""
views.py — Endpoints de MS-Reportes

Endpoints implementados:
  GET  /api/v1/health/                           — Health check
  GET  /api/v1/reportes/consolidado/             — Reporte consolidado (ASR Latencia + Seguridad)
  GET  /api/v1/reportes/historial/               — Historial de reportes generados
  GET  /api/v1/reportes/consolidado/sin-cache/   — Reporte forzando bypass de caché (experimento)

  --- Experimento Seguridad (ASR2) ---
  GET  /api/v1/seguridad/consolidado-vulnerable/ — Fase 1: endpoint INSEGURO (demostración)
  GET  /api/v1/seguridad/consolidado-protegido/  — Fase 2: endpoint SEGURO con ORM

  --- Experimento Mantenibilidad (ASR3) ---
  POST /api/v1/recursos/                         — Crear recurso cloud (seed datos)
  GET  /api/v1/recursos/                         — Listar recursos activos
  GET  /api/v1/recursos/costo-bajo-demanda/      — calcular_costo_instancias_bajo_demanda
"""

import logging
from datetime import datetime

from django.db import connection
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Reporte, RecursoCloud
from .serializers import ReporteSerializer, RecursoCloudSerializer, RecursoCloudCreateSerializer
from .validators import validar_proyecto_id, validar_fecha, validar_rango_fechas
from .services import reporte_orchestrator, analizador

logger = logging.getLogger(__name__)


# ===========================================================================
# HEALTH CHECK
# ===========================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def health(request):
    return Response({'status': 'ok', 'servicio': 'ms-reportes'}, status=status.HTTP_200_OK)


# ===========================================================================
# REPORTE CONSOLIDADO — ASR Latencia + Seguridad (endpoint principal)
# ===========================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def reporte_consolidado(request):
    """
    GET /api/v1/reportes/consolidado/
    Parámetros: proyecto_id, fecha_inicio (YYYY-MM-DD), fecha_fin (YYYY-MM-DD)

    Tácticas aplicadas:
    - Input Validation (ASR Seguridad): proyecto_id validado antes de cualquier uso.
    - Caché Redis (ASR Latencia): hit → < 1s; miss → consulta distribuida.
    - API Composition: orquesta MS-Empresas + MS-Consumos.
    - Prepared Statements: ORM Django para persistencia en PostgreSQL.
    """
    # --- Validación de inputs (Táctica ASR Seguridad) ---
    try:
        proyecto_id = validar_proyecto_id(request.query_params.get('proyecto_id', ''))
        fecha_inicio = validar_fecha(request.query_params.get('fecha_inicio', ''), 'fecha_inicio')
        fecha_fin = validar_fecha(request.query_params.get('fecha_fin', ''), 'fecha_fin')
        validar_rango_fechas(fecha_inicio, fecha_fin)
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    # --- Extraer token JWT para reenvío a MS-Empresas ---
    auth_header = request.headers.get('Authorization', '')
    token = auth_header.replace('Bearer ', '').strip()

    # --- Orquestación con caché (Táctica ASR Latencia) ---
    try:
        reporte = reporte_orchestrator.generar_reporte(
            proyecto_id=proyecto_id,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            token=token,
            usar_cache=True,
        )
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)
    except (TimeoutError, ConnectionError) as exc:
        return Response(
            {'error': f'Error de conectividad entre microservicios: {exc}'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except Exception as exc:
        logger.exception("Error inesperado al generar reporte")
        return Response(
            {'error': 'Error interno del servidor.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # --- Persistir en PostgreSQL para auditoría (ORM = prepared statements) ---
    _persistir_reporte(reporte, proyecto_id, fecha_inicio, fecha_fin)

    return Response(reporte, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def reporte_consolidado_sin_cache(request):
    """
    GET /api/v1/reportes/consolidado/sin-cache/
    Igual al anterior pero fuerza el bypass del caché.
    Usado en el experimento JMeter — Fase 1 (sin caché).
    """
    try:
        proyecto_id = validar_proyecto_id(request.query_params.get('proyecto_id', ''))
        fecha_inicio = validar_fecha(request.query_params.get('fecha_inicio', ''), 'fecha_inicio')
        fecha_fin = validar_fecha(request.query_params.get('fecha_fin', ''), 'fecha_fin')
        validar_rango_fechas(fecha_inicio, fecha_fin)
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    auth_header = request.headers.get('Authorization', '')
    token = auth_header.replace('Bearer ', '').strip()

    try:
        reporte = reporte_orchestrator.generar_reporte(
            proyecto_id=proyecto_id,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            token=token,
            usar_cache=False,   # ← bypass explícito
        )
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)
    except (TimeoutError, ConnectionError) as exc:
        return Response({'error': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception:
        logger.exception("Error inesperado al generar reporte (sin caché)")
        return Response({'error': 'Error interno.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    _persistir_reporte(reporte, proyecto_id, fecha_inicio, fecha_fin)
    return Response(reporte, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def historial_reportes(request):
    """GET /api/v1/reportes/historial/ — Lista los últimos 100 reportes."""
    proyecto_id = request.query_params.get('proyecto_id')
    qs = Reporte.objects.all()[:100]
    if proyecto_id:
        # ORM filtra con prepared statement — safe by default
        qs = Reporte.objects.filter(proyecto_id=proyecto_id)[:100]
    serializer = ReporteSerializer(qs, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


def _persistir_reporte(reporte: dict, proyecto_id, fecha_inicio, fecha_fin):
    """Helper privado para persistir el reporte en PostgreSQL vía ORM."""
    try:
        Reporte.objects.create(
            proyecto_id=proyecto_id,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            proyecto_nombre=reporte.get('proyecto_nombre', ''),
            empresa_nombre=reporte.get('empresa_nombre', ''),
            presupuesto=reporte.get('presupuesto', 0),
            total_registros=reporte.get('total_registros', 0),
            costo_total=reporte.get('costo_total', 0),
            estado=Reporte.Estado.EXITOSO,
            desde_cache=reporte.get('desde_cache', False),
        )
    except Exception as exc:
        logger.warning("No se pudo persistir el reporte: %s", exc)


# ===========================================================================
# EXPERIMENTO SEGURIDAD — ASR2: SQL Injection
# Fase 1: Endpoint VULNERABLE (concatenación de strings — solo para demo)
# Fase 2: Endpoint PROTEGIDO (ORM Django con prepared statements)
# ===========================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def consolidado_vulnerable(request):
    """
    GET /api/v1/seguridad/consolidado-vulnerable/

    ⚠️  FASE 1 DEL EXPERIMENTO — CÓDIGO INTENCIONALMENTE INSEGURO ⚠️
    Construye SQL por concatenación directa de strings.
    Con project_id=' OR '1'='1'-- retorna todos los proyectos de todos
    los tenants. Usado únicamente para demostrar la vulnerabilidad.

    NO usar en producción.
    """
    proyecto_id_raw = request.query_params.get('proyecto_id', '')

    # ❌ SQL por concatenación — VULNERABLE a SQL Injection
    sql_inseguro = (
        "SELECT id, proyecto_id, fecha_inicio, fecha_fin, costo_total "
        "FROM reportes "
        f"WHERE proyecto_id = '{proyecto_id_raw}' "
        "ORDER BY generado_en DESC LIMIT 50"
    )

    try:
        with connection.cursor() as cursor:
            cursor.execute(sql_inseguro)
            columnas = [col[0] for col in cursor.description]
            filas = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({
        'advertencia': 'ENDPOINT VULNERABLE — solo para experimento ASR Seguridad Fase 1',
        'proyecto_id_recibido': proyecto_id_raw,
        'total_filas': len(filas),
        'datos': filas,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def consolidado_protegido(request):
    """
    GET /api/v1/seguridad/consolidado-protegido/

    ✅  FASE 2 DEL EXPERIMENTO — ENDPOINT SEGURO ✅
    Valida proyecto_id con regex y usa el ORM de Django (.filter()),
    que genera prepared statements automáticamente.

    Con project_id=' OR '1'='1'-- retorna HTTP 400 — tasa de éxito ataque = 0%.
    """
    # Validación estricta (Táctica Input Validation)
    try:
        proyecto_id = validar_proyecto_id(request.query_params.get('proyecto_id', ''))
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    # ORM Django → prepared statement automático
    reportes = (
        Reporte.objects
        .filter(proyecto_id=proyecto_id)  # ← safe by default
        .order_by('-generado_en')[:50]
    )
    serializer = ReporteSerializer(reportes, many=True)

    return Response({
        'proyecto_id': proyecto_id,
        'total_filas': len(serializer.data),
        'datos': serializer.data,
    }, status=status.HTTP_200_OK)


# ===========================================================================
# EXPERIMENTO MANTENIBILIDAD — ASR3: Analizador de Recursos Cloud
# ===========================================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def recursos_cloud(request):
    """
    GET  /api/v1/recursos/  — Lista recursos activos (filtra por proyecto_id)
    POST /api/v1/recursos/  — Crea un recurso cloud (seeding para experimento)
    """
    if request.method == 'GET':
        proyecto_id = request.query_params.get('proyecto_id')
        if proyecto_id:
            try:
                proyecto_id = validar_proyecto_id(proyecto_id)
            except ValueError as exc:
                return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            recursos = RecursoCloud.objects.filter(proyecto_id=proyecto_id, activo=True)
        else:
            recursos = RecursoCloud.objects.filter(activo=True)[:200]
        serializer = RecursoCloudSerializer(recursos, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # POST
    serializer = RecursoCloudCreateSerializer(data=request.data)
    if serializer.is_valid():
        recurso = serializer.save()
        return Response(RecursoCloudSerializer(recurso).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def costo_bajo_demanda(request):
    """
    GET /api/v1/recursos/costo-bajo-demanda/
    Parámetros: proyecto_id, fecha_inicio, fecha_fin

    Invoca AnalizadorRecursosCloud.calcular_costo_instancias_bajo_demanda
    Experimento ASR3: complejidad ciclomática < 10, duplicación 0%.
    """
    try:
        proyecto_id = validar_proyecto_id(request.query_params.get('proyecto_id', ''))
        fecha_inicio = validar_fecha(request.query_params.get('fecha_inicio', ''), 'fecha_inicio')
        fecha_fin = validar_fecha(request.query_params.get('fecha_fin', ''), 'fecha_fin')
        validar_rango_fechas(fecha_inicio, fecha_fin)
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    resultado = analizador.calcular_costo_instancias_bajo_demanda(
        proyecto_id=proyecto_id,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )
    return Response(resultado, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def recursos_activos(request):
    """
    GET /api/v1/recursos/activos/?proyecto_id=...
    Método preexistente: listar_recursos_activos (línea base SonarQube).
    """
    try:
        proyecto_id = validar_proyecto_id(request.query_params.get('proyecto_id', ''))
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    recursos = analizador.listar_recursos_activos(proyecto_id)
    return Response({'proyecto_id': proyecto_id, 'recursos': recursos}, status=status.HTTP_200_OK)
