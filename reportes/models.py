import uuid
from django.db import models


class Reporte(models.Model):
    """
    Registro de cada reporte consolidado generado por MS-Reportes.
    Persiste el resultado para auditoría y trazabilidad.

    Táctica ASR-Seguridad: proyecto_id se almacena como CharField
    ya que los IDs del sistema son strings como 'proyecto-1'.
    El ORM de Django usa prepared statements automáticamente,
    eliminando SQL Injection por diseño.
    """

    class Estado(models.TextChoices):
        EXITOSO = 'exitoso', 'Exitoso'
        ERROR = 'error', 'Error'

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    # proyecto_id como string — los IDs son 'proyecto-1' .. 'proyecto-10'
    # db_index=True para búsquedas eficientes (ASR latencia)
    proyecto_id = models.CharField(max_length=100, db_index=True)

    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()

    # Metadatos del proyecto provenientes de MS-Empresas
    proyecto_nombre = models.CharField(max_length=255, blank=True)
    empresa_nombre = models.CharField(max_length=255, blank=True)
    presupuesto = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )

    # Métricas consolidadas del reporte
    total_registros = models.IntegerField(default=0)
    costo_total = models.DecimalField(
        max_digits=14, decimal_places=2, default=0
    )

    estado = models.CharField(
        max_length=10,
        choices=Estado.choices,
        default=Estado.EXITOSO,
    )
    mensaje_error = models.TextField(blank=True)
    generado_en = models.DateTimeField(auto_now_add=True)

    # Indica si este reporte fue servido desde caché Redis (para métricas)
    desde_cache = models.BooleanField(default=False)

    class Meta:
        db_table = 'reportes'
        ordering = ['-generado_en']
        indexes = [
            models.Index(fields=['proyecto_id', 'fecha_inicio', 'fecha_fin']),
        ]

    def __str__(self):
        return f'Reporte {self.proyecto_id} [{self.fecha_inicio} – {self.fecha_fin}]'


class RecursoCloud(models.Model):
    """
    Modelo para el experimento de Mantenibilidad (ASR3).
    Representa un recurso cloud registrado por proyecto.
    El método calcular_costo_instancias_bajo_demanda opera sobre esta tabla.

    Táctica Reducción de Acoplamiento: el nuevo método se agrega en
    services.py como función independiente sin tocar este modelo.
    """

    class TipoInstancia(models.TextChoices):
        T2_MICRO = 't2.micro', 't2.micro'
        T2_SMALL = 't2.small', 't2.small'
        T2_MEDIUM = 't2.medium', 't2.medium'
        T3_MICRO = 't3.micro', 't3.micro'
        T3_SMALL = 't3.small', 't3.small'
        T3_MEDIUM = 't3.medium', 't3.medium'
        M5_LARGE = 'm5.large', 'm5.large'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    proyecto_id = models.CharField(max_length=100, db_index=True)
    tipo_instancia = models.CharField(
        max_length=20,
        choices=TipoInstancia.choices,
        default=TipoInstancia.T2_MICRO,
    )
    cantidad = models.IntegerField(default=1)
    horas_uso = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    fecha_registro = models.DateField()
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'recursos_cloud'
        ordering = ['-fecha_registro']

    def __str__(self):
        return f'{self.tipo_instancia} x{self.cantidad} — {self.proyecto_id}'
