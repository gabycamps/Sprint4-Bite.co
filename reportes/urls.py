from django.urls import path
from . import views

urlpatterns = [
    # Health check
    path('health/', views.health, name='health'),

    # --- Reporte consolidado (ASR Latencia + Seguridad) ---
    path('reportes/consolidado/', views.reporte_consolidado, name='reporte-consolidado'),
    path('reportes/consolidado/sin-cache/', views.reporte_consolidado_sin_cache, name='reporte-sin-cache'),
    path('reportes/historial/', views.historial_reportes, name='historial-reportes'),

    # --- Experimento Seguridad ASR2 ---
    path('seguridad/consolidado-vulnerable/', views.consolidado_vulnerable, name='vulnerable'),
    path('seguridad/consolidado-protegido/', views.consolidado_protegido, name='protegido'),

    # --- Experimento Mantenibilidad ASR3 ---
    path('recursos/', views.recursos_cloud, name='recursos-cloud'),
    path('recursos/activos/', views.recursos_activos, name='recursos-activos'),
    path('recursos/costo-bajo-demanda/', views.costo_bajo_demanda, name='costo-bajo-demanda'),
]
