from django.contrib import admin
from .models import Reporte, RecursoCloud


@admin.register(Reporte)
class ReporteAdmin(admin.ModelAdmin):
    list_display = ['proyecto_id', 'fecha_inicio', 'fecha_fin', 'costo_total', 'desde_cache', 'generado_en']
    list_filter = ['estado', 'desde_cache']
    search_fields = ['proyecto_id', 'empresa_nombre']


@admin.register(RecursoCloud)
class RecursoCloudAdmin(admin.ModelAdmin):
    list_display = ['proyecto_id', 'tipo_instancia', 'cantidad', 'horas_uso', 'fecha_registro', 'activo']
    list_filter = ['tipo_instancia', 'activo']
    search_fields = ['proyecto_id']
