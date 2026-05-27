from django.urls import path
from . import views

urlpatterns = [
    # ------------------------------------------------------------------
    # Health Check
    # ------------------------------------------------------------------
    path('health/', views.health, name='health'),

    # ------------------------------------------------------------------
    # CRUD — Empresa
    # ------------------------------------------------------------------
    path('empresas/', views.empresa_list_create, name='empresa-list-create'),
    path('empresas/<uuid:pk>/', views.empresa_retrieve_update_destroy, name='empresa-detail'),

    # ------------------------------------------------------------------
    # CRUD — Proyecto
    # GET /proyectos/?empresa_id=<uuid>  →  filtra por empresa
    # ------------------------------------------------------------------
    path('proyectos/', views.proyecto_list_create, name='proyecto-list-create'),
    path('proyectos/<uuid:pk>/', views.proyecto_retrieve_update_destroy, name='proyecto-detail'),

    # ------------------------------------------------------------------
    # Endpoint Interno — Batch (API Composition para MS-Reportes)
    # GET /internal/proyectos/batch/?ids=uuid1,uuid2&solo_activos=true
    # ------------------------------------------------------------------
    path('internal/proyectos/batch/', views.proyectos_batch, name='proyectos-batch'),
]
