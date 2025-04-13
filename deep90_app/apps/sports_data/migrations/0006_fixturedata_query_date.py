# Generated by Django 5.1.8 on 2025-04-13 03:46

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sports_data', '0005_fixturedata_leaguedata_standingdata'),
    ]

    operations = [
        migrations.AddField(
            model_name='fixturedata',
            name='query_date',
            field=models.DateTimeField(default=django.utils.timezone.now, verbose_name='Fecha de consulta'),
        ),
    ]
