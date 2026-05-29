from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Reporte',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('proyecto_id', models.CharField(db_index=True, max_length=100)),
                ('fecha_inicio', models.DateField()),
                ('fecha_fin', models.DateField()),
                ('proyecto_nombre', models.CharField(blank=True, max_length=255)),
                ('empresa_nombre', models.CharField(blank=True, max_length=255)),
                ('presupuesto', models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ('total_registros', models.IntegerField(default=0)),
                ('costo_total', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('estado', models.CharField(
                    choices=[('exitoso', 'Exitoso'), ('error', 'Error')],
                    default='exitoso', max_length=10,
                )),
                ('mensaje_error', models.TextField(blank=True)),
                ('generado_en', models.DateTimeField(auto_now_add=True)),
                ('desde_cache', models.BooleanField(default=False)),
            ],
            options={'db_table': 'reportes', 'ordering': ['-generado_en']},
        ),
        migrations.AddIndex(
            model_name='reporte',
            index=models.Index(fields=['proyecto_id', 'fecha_inicio', 'fecha_fin'], name='reportes_proyecto_fechas_idx'),
        ),
        migrations.CreateModel(
            name='RecursoCloud',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('proyecto_id', models.CharField(db_index=True, max_length=100)),
                ('tipo_instancia', models.CharField(
                    choices=[
                        ('t2.micro', 't2.micro'), ('t2.small', 't2.small'), ('t2.medium', 't2.medium'),
                        ('t3.micro', 't3.micro'), ('t3.small', 't3.small'), ('t3.medium', 't3.medium'),
                        ('m5.large', 'm5.large'),
                    ],
                    default='t2.micro', max_length=20,
                )),
                ('cantidad', models.IntegerField(default=1)),
                ('horas_uso', models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('fecha_registro', models.DateField()),
                ('activo', models.BooleanField(default=True)),
            ],
            options={'db_table': 'recursos_cloud', 'ordering': ['-fecha_registro']},
        ),
    ]
