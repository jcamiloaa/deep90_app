# Generated by Django 5.1.8 on 2025-04-12 22:37

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sports_data', '0002_alter_scheduledtask_status'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SyncConfiguration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Nombre descriptivo para esta configuración', max_length=100, verbose_name='Nombre')),
                ('selected_items', models.JSONField(blank=True, help_text='IDs y parámetros de los elementos seleccionados para sincronizar', null=True, verbose_name='Elementos seleccionados')),
                ('periodicity', models.CharField(choices=[('hourly', 'Cada hora'), ('daily', 'Diaria'), ('weekly', 'Semanal'), ('monthly', 'Mensual'), ('custom', 'Personalizada')], default='daily', max_length=20, verbose_name='Periodicidad')),
                ('custom_interval', models.PositiveIntegerField(blank=True, help_text='Intervalo en minutos para periodicidad personalizada', null=True, verbose_name='Intervalo personalizado (minutos)')),
                ('last_synced', models.DateTimeField(blank=True, null=True, verbose_name='Última sincronización')),
                ('active', models.BooleanField(default=True, help_text='Indica si esta configuración está activa para sincronización', verbose_name='Activo')),
                ('celery_task_id', models.CharField(blank=True, max_length=100, null=True, verbose_name='ID tarea Celery')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Última modificación')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sync_configurations', to=settings.AUTH_USER_MODEL, verbose_name='Creado por')),
                ('endpoint', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sync_configurations', to='sports_data.apiendpoint', verbose_name='Endpoint')),
            ],
            options={
                'verbose_name': 'Configuración de sincronización',
                'verbose_name_plural': 'Configuraciones de sincronización',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='SyncResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('execution_time', models.FloatField(help_text='Tiempo total de ejecución de la sincronización en segundos', verbose_name='Tiempo total de ejecución (seg)')),
                ('api_response_time', models.FloatField(help_text='Tiempo que tardó la API en responder en segundos', verbose_name='Tiempo de respuesta API (seg)')),
                ('records_created', models.IntegerField(default=0, verbose_name='Registros creados')),
                ('records_updated', models.IntegerField(default=0, verbose_name='Registros actualizados')),
                ('records_skipped', models.IntegerField(default=0, verbose_name='Registros omitidos')),
                ('executed_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de ejecución')),
                ('success', models.BooleanField(default=True, verbose_name='Éxito')),
                ('errors', models.JSONField(blank=True, help_text='Lista de errores encontrados durante la sincronización', null=True, verbose_name='Errores')),
                ('configuration', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='results', to='sports_data.syncconfiguration', verbose_name='Configuración')),
            ],
            options={
                'verbose_name': 'Resultado de sincronización',
                'verbose_name_plural': 'Resultados de sincronización',
                'ordering': ['-executed_at'],
            },
        ),
    ]
