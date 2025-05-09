# Generated by Django 5.1.8 on 2025-04-14 04:14

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConversationSummary',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('summary', models.TextField(verbose_name='Resumen de la conversación')),
                ('key_points', models.JSONField(default=list, verbose_name='Puntos clave')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Fecha de creación')),
                ('conversation', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='summary', to='whatsapp.conversation', verbose_name='Conversación')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conversation_summaries', to='whatsapp.whatsappuser', verbose_name='Usuario')),
            ],
            options={
                'verbose_name': 'Resumen de conversación',
                'verbose_name_plural': 'Resúmenes de conversaciones',
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['user'], name='whatsapp_co_user_id_d647dc_idx'), models.Index(fields=['created_at'], name='whatsapp_co_created_8a465c_idx')],
            },
        ),
    ]
