from rest_framework import serializers
from .models import Empresa, Proyecto


# ---------------------------------------------------------------------------
# Empresa
# ---------------------------------------------------------------------------

class EmpresaSerializer(serializers.ModelSerializer):
    """Serializer completo para operaciones CRUD de Empresa."""

    class Meta:
        model = Empresa
        fields = ['id', 'nombre', 'nit_o_rut', 'estado', 'fecha_registro']
        read_only_fields = ['id', 'fecha_registro']


class EmpresaCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer de escritura para Empresa (excluye campos de solo lectura)."""

    class Meta:
        model = Empresa
        fields = ['nombre', 'nit_o_rut', 'estado']


# ---------------------------------------------------------------------------
# Proyecto
# ---------------------------------------------------------------------------

class ProyectoSerializer(serializers.ModelSerializer):
    """Serializer completo para operaciones CRUD de Proyecto."""

    empresa_nombre = serializers.CharField(source='empresa.nombre', read_only=True)

    class Meta:
        model = Proyecto
        fields = [
            'id', 'empresa', 'empresa_nombre',
            'nombre', 'presupuesto', 'cloud_account_id',
            'estado', 'fecha_creacion',
        ]
        read_only_fields = ['id', 'fecha_creacion', 'empresa_nombre']


class ProyectoCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer de escritura para Proyecto."""

    class Meta:
        model = Proyecto
        fields = ['empresa', 'nombre', 'presupuesto', 'cloud_account_id', 'estado']


# ---------------------------------------------------------------------------
# Endpoint Interno — Batch (consumido por MS-Reportes)
# ---------------------------------------------------------------------------

class ProyectoBatchSerializer(serializers.ModelSerializer):
    """
    Serializer optimizado para el endpoint de orquestación interna.
    Incluye los metadatos del proyecto y el nombre de la empresa
    (evita N+1 porque la vista usa select_related).
    """

    empresa_id = serializers.UUIDField(source='empresa.id', read_only=True)
    empresa_nombre = serializers.CharField(source='empresa.nombre', read_only=True)

    class Meta:
        model = Proyecto
        fields = [
            'id', 'nombre', 'presupuesto', 'cloud_account_id',
            'estado', 'fecha_creacion',
            'empresa_id', 'empresa_nombre',
        ]
