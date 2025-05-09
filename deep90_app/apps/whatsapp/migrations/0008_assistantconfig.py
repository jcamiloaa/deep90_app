# Generated by Django 5.1.8 on 2025-05-06 21:19

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp', '0007_conversation_conversation_type_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='AssistantConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('assistant_name', models.CharField(default='Deep90 AI', max_length=50, verbose_name='Nombre del asistente')),
                ('language_style', models.CharField(choices=[('tecnico', 'Técnico'), ('normal', 'Normal')], default='normal', max_length=20, verbose_name='Estilo de lenguaje')),
                ('experience_level', models.CharField(choices=[('baja', 'Baja'), ('media', 'Media'), ('alta', 'Alta')], default='media', max_length=10, verbose_name='Nivel de experiencia')),
                ('prediction_types', models.JSONField(blank=True, default=list, help_text='Lista de tipos de predicción seleccionados', verbose_name='Tipos de predicciones preferidas')),
                ('custom_settings', models.JSONField(blank=True, default=dict, verbose_name='Configuraciones adicionales')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Última actualización')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='assistant_config', to='whatsapp.whatsappuser', verbose_name='Usuario')),
            ],
            options={
                'verbose_name': 'Configuración de Asistente',
                'verbose_name_plural': 'Configuraciones de Asistente',
            },
        ),
    ]
