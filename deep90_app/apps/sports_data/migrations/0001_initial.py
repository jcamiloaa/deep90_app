# Generated by Django 5.1.8 on 2025-04-09 22:49

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='APIEndpoint',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Nombre')),
                ('endpoint', models.CharField(max_length=200, verbose_name='Endpoint')),
                ('description', models.TextField(blank=True, verbose_name='Descripción')),
                ('has_parameters', models.BooleanField(default=False, verbose_name='Tiene parámetros')),
            ],
            options={
                'verbose_name': 'Endpoint API',
                'verbose_name_plural': 'Endpoints API',
            },
        ),
        migrations.CreateModel(
            name='APIParameter',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Nombre')),
                ('parameter_type', models.CharField(choices=[('integer', 'Entero'), ('string', 'Texto'), ('boolean', 'Booleano')], max_length=20, verbose_name='Tipo de parámetro')),
                ('required', models.BooleanField(default=False, verbose_name='Requerido')),
                ('description', models.TextField(blank=True, verbose_name='Descripción')),
                ('endpoint', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='parameters', to='sports_data.apiendpoint', verbose_name='Endpoint')),
            ],
            options={
                'verbose_name': 'Parámetro API',
                'verbose_name_plural': 'Parámetros API',
            },
        ),
        migrations.CreateModel(
            name='ScheduledTask',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Nombre')),
                ('parameters', models.JSONField(blank=True, null=True, verbose_name='Parámetros')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')),
                ('scheduled_time', models.DateTimeField(blank=True, null=True, verbose_name='Fecha programada')),
                ('status', models.CharField(choices=[('pending', 'Pendiente'), ('running', 'En ejecución'), ('success', 'Completado'), ('failed', 'Fallido')], default='pending', max_length=20, verbose_name='Estado')),
                ('schedule_type', models.CharField(choices=[('immediate', 'Inmediata'), ('scheduled', 'Programada'), ('periodic', 'Periódica')], default='immediate', max_length=20, verbose_name='Tipo de programación')),
                ('periodic_interval', models.PositiveIntegerField(blank=True, null=True, verbose_name='Intervalo periódico (minutos)')),
                ('celery_task_id', models.CharField(blank=True, max_length=100, null=True, verbose_name='ID tarea Celery')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='created_tasks', to=settings.AUTH_USER_MODEL, verbose_name='Creado por')),
                ('endpoint', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tasks', to='sports_data.apiendpoint', verbose_name='Endpoint')),
            ],
            options={
                'verbose_name': 'Tarea programada',
                'verbose_name_plural': 'Tareas programadas',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='APIResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('executed_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de ejecución')),
                ('response_code', models.IntegerField(verbose_name='Código de respuesta')),
                ('response_data', models.JSONField(blank=True, null=True, verbose_name='Datos de respuesta')),
                ('execution_time', models.FloatField(blank=True, null=True, verbose_name='Tiempo de ejecución (seg)')),
                ('success', models.BooleanField(default=True, verbose_name='Éxito')),
                ('error_message', models.TextField(blank=True, null=True, verbose_name='Mensaje de error')),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='results', to='sports_data.scheduledtask', verbose_name='Tarea')),
            ],
            options={
                'verbose_name': 'Resultado API',
                'verbose_name_plural': 'Resultados API',
                'ordering': ['-executed_at'],
            },
        ),
    ]
