# Generated by Django 5.1.8 on 2025-04-14 21:28

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp', '0003_conversation_end_time_conversation_summary_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='conversation',
            name='end_time',
        ),
        migrations.RemoveField(
            model_name='conversation',
            name='summary',
        ),
        migrations.DeleteModel(
            name='ConversationSummary',
        ),
    ]
