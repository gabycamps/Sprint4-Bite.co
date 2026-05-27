from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Empresa, Proyecto
from .serializers import (
    EmpresaSerializer,
    EmpresaCreateUpdateSerializer,
    ProyectoSerializer,
    ProyectoCreateUpdateSerializer,
    ProyectoBatchSerializer,
)


# ===========================================================================
# HEALTH CHECK
# ===========================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def health(request):
    """Endpoint de salud para load balancer / Kong."""
    return Response({'status': 'ok'}, status=status.HTTP_200_OK)


# ===========================================================================
# EMPRESA — CRUD
# ===========================================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def empresa_list_create(request):
    """
    GET  /api/v1/empresas/       → Lista todas las empresas.
    POST /api/v1/empresas/       → Crea una empresa nueva.
    """
    if request.method == 'GET':
        empresas = Empresa.objects.all()
        serializer = EmpresaSerializer(empresas, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    serializer = EmpresaCreateUpdateSerializer(data=request.data)
    if serializer.is_valid():
        empresa = serializer.save()
        return Response(
            EmpresaSerializer(empresa).data,
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def empresa_retrieve_update_destroy(request, pk):
    """
    GET    /api/v1/empresas/<uuid>/  → Detalle.
    PUT    /api/v1/empresas/<uuid>/  → Actualización completa.
    PATCH  /api/v1/empresas/<uuid>/  → Actualización parcial.
    DELETE /api/v1/empresas/<uuid>/  → Eliminación (falla si tiene proyectos).
    """
    try:
        empresa = Empresa.objects.get(pk=pk)
    except Empresa.DoesNotExist:
        return Response({'error': 'Empresa no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(EmpresaSerializer(empresa).data, status=status.HTTP_200_OK)

    if request.method in ('PUT', 'PATCH'):
        partial = request.method == 'PATCH'
        serializer = EmpresaCreateUpdateSerializer(empresa, data=request.data, partial=partial)
        if serializer.is_valid():
            empresa = serializer.save()
            return Response(EmpresaSerializer(empresa).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # DELETE
    try:
        empresa.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    except Exception:
        return Response(
            {'error': 'No se puede eliminar una empresa con proyectos asociados.'},
            status=status.HTTP_409_CONFLICT,
        )


# ===========================================================================
# PROYECTO — CRUD
# ===========================================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def proyecto_list_create(request):
    """
    GET  /api/v1/proyectos/  → Lista todos los proyectos.
    POST /api/v1/proyectos/  → Crea un proyecto.
    Soporta filtro por empresa: ?empresa_id=<uuid>
    """
    if request.method == 'GET':
        qs = Proyecto.objects.select_related('empresa').all()
        empresa_id = request.query_params.get('empresa_id')
        if empresa_id:
            qs = qs.filter(empresa__id=empresa_id)
        serializer = ProyectoSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    serializer = ProyectoCreateUpdateSerializer(data=request.data)
    if serializer.is_valid():
        proyecto = serializer.save()
        # Recargar con select_related para incluir empresa_nombre en respuesta
        proyecto = Proyecto.objects.select_related('empresa').get(pk=proyecto.pk)
        return Response(
            ProyectoSerializer(proyecto).data,
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def proyecto_retrieve_update_destroy(request, pk):
    """
    GET    /api/v1/proyectos/<uuid>/  → Detalle.
    PUT    /api/v1/proyectos/<uuid>/  → Actualización completa.
    PATCH  /api/v1/proyectos/<uuid>/  → Actualización parcial.
    DELETE /api/v1/proyectos/<uuid>/  → Eliminación.
    """
    try:
        proyecto = Proyecto.objects.select_related('empresa').get(pk=pk)
    except Proyecto.DoesNotExist:
        return Response({'error': 'Proyecto no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(ProyectoSerializer(proyecto).data, status=status.HTTP_200_OK)

    if request.method in ('PUT', 'PATCH'):
        partial = request.method == 'PATCH'
        serializer = ProyectoCreateUpdateSerializer(proyecto, data=request.data, partial=partial)
        if serializer.is_valid():
            proyecto = serializer.save()
            proyecto = Proyecto.objects.select_related('empresa').get(pk=proyecto.pk)
            return Response(ProyectoSerializer(proyecto).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # DELETE
    proyecto.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ===========================================================================
# ENDPOINT INTERNO — BATCH (consumido por MS-Reportes vía API Composition)
# ===========================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def proyectos_batch(request):
    """
    GET /api/v1/internal/proyectos/batch/?ids=uuid1,uuid2&solo_activos=true

    Endpoint de orquestación interna para MS-Reportes.
    - Recibe una lista de UUIDs separados por coma.
    - Filtra opcionalmente por proyectos con estado='activo' si solo_activos=true.
    - Los IDs que no existen se omiten silenciosamente (sin 404).
    - Usa select_related('empresa') para evitar el problema N+1.
    - Retorna un JSON estructurado con metadatos de proyecto y empresa.
    """
    ids_raw = request.query_params.get('ids', '')
    solo_activos = request.query_params.get('solo_activos', 'false').lower() == 'true'

    if not ids_raw:
        return Response(
            {'error': 'El parámetro "ids" es requerido.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Parsear y validar UUIDs — los malformados se descartan sin error
    import uuid as uuid_lib
    uuids_validos = []
    for raw_id in ids_raw.split(','):
        raw_id = raw_id.strip()
        try:
            uuids_validos.append(uuid_lib.UUID(raw_id))
        except ValueError:
            pass  # UUID malformado: se ignora

    # Consulta principal — una sola query SQL con JOIN (select_related)
    qs = (
        Proyecto.objects
        .select_related('empresa')
        .filter(id__in=uuids_validos)
    )

    if solo_activos:
        qs = qs.filter(estado=Proyecto.Estado.ACTIVO)

    serializer = ProyectoBatchSerializer(qs, many=True)

    return Response(
        {
            'count': len(serializer.data),
            'solo_activos': solo_activos,
            'proyectos': serializer.data,
        },
        status=status.HTTP_200_OK,
    )
