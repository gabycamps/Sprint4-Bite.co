from rest_framework import serializers
from .models import Reporte, RecursoCloud


class ReporteSerializer(serializers.ModelSerializer):
    """Serializer de lectura para el historial de reportes."""

    class Meta:
        model = Reporte
        fields = [
            'id', 'proyecto_id', 'fecha_inicio', 'fecha_fin',
            'proyecto_nombre', 'empresa_nombre', 'presupuesto',
            'total_registros', 'costo_total', 'estado',
            'desde_cache', 'generado_en',
        ]
        read_only_fields = fields


class RecursoCloudSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecursoCloud
        fields = [
            'id', 'proyecto_id', 'tipo_instancia', 'cantidad',
            'horas_uso', 'fecha_registro', 'activo',
        ]
        read_only_fields = ['id']


class RecursoCloudCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecursoCloud
        fields = ['proyecto_id', 'tipo_instancia', 'cantidad', 'horas_uso', 'fecha_registro']
