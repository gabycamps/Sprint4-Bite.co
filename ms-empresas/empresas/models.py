import uuid
from django.db import models


class Empresa(models.Model):
    """
    Representa una empresa registrada en la plataforma Bite.co.
    Usa UUID4 como PK para evitar enumeración y mejorar seguridad.
    """

    class Estado(models.TextChoices):
        ACTIVO = 'activo', 'Activo'
        INACTIVO = 'inactivo', 'Inactivo'

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    nombre = models.CharField(max_length=255, unique=True)
    nit_o_rut = models.CharField(max_length=50, unique=True)
    estado = models.CharField(
        max_length=10,
        choices=Estado.choices,
        default=Estado.ACTIVO,
    )
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'empresas'
        ordering = ['nombre']

    def __str__(self):
        return f'{self.nombre} ({self.nit_o_rut})'


class Proyecto(models.Model):
    """
    Proyecto asociado a una Empresa.
    - cloud_account_id indexado para búsquedas eficientes.
    - ON DELETE PROTECT: no se puede eliminar una empresa con proyectos.
    """

    class Estado(models.TextChoices):
        ACTIVO = 'activo', 'Activo'
        INACTIVO = 'inactivo', 'Inactivo'
        SUSPENDIDO = 'suspendido', 'Suspendido'

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.PROTECT,
        related_name='proyectos',
    )
    nombre = models.CharField(max_length=255)
    presupuesto = models.DecimalField(max_digits=14, decimal_places=2)
    cloud_account_id = models.CharField(max_length=100, db_index=True)
    estado = models.CharField(
        max_length=12,
        choices=Estado.choices,
        default=Estado.ACTIVO,
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'proyectos'
        ordering = ['nombre']

    def __str__(self):
        return f'{self.nombre} — {self.empresa.nombre}'
