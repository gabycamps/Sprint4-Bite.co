from django.contrib import admin
from .models import Empresa, Proyecto


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'nit_o_rut', 'estado', 'fecha_registro']
    list_filter = ['estado']
    search_fields = ['nombre', 'nit_o_rut']
    readonly_fields = ['id', 'fecha_registro']
    ordering = ['nombre']


@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'empresa', 'presupuesto', 'cloud_account_id', 'estado', 'fecha_creacion']
    list_filter = ['estado', 'empresa']
    search_fields = ['nombre', 'cloud_account_id', 'empresa__nombre']
    readonly_fields = ['id', 'fecha_creacion']
    ordering = ['empresa', 'nombre']
    autocomplete_fields = ['empresa']
