import os

from celery import Celery
from celery.signals import setup_logging
from celery.schedules import crontab

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("deep90_app")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")


@setup_logging.connect
def config_loggers(*args, **kwargs):
    from logging.config import dictConfig

    from django.conf import settings

    dictConfig(settings.LOGGING)


# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# Configure periodic tasks
app.conf.beat_schedule = {
    # Tarea para programar la ejecución de tareas API de fútbol
    "schedule-api-football-tasks": {
        "task": "deep90_app.apps.sports_data.tasks.schedule_periodic_tasks",
        "schedule": crontab(minute="*/5"),  # Cada 5 minutos
    },
    # Tarea para supervisar la ejecución de tareas en vivo
    "schedule-live-football-tasks": {
        "task": "deep90_app.apps.sports_data.live_tasks.schedule_live_tasks",
        "schedule": crontab(minute="*"),  # Cada minuto
    },
    # Nueva tarea para verificar y corregir tareas desincronizadas
    "check-stalled-tasks": {
        "task": "deep90_app.apps.sports_data.live_tasks.check_and_reset_stalled_tasks",
        "schedule": crontab(minute="*/3"),  # Cada 3 minutos
        "options": {"expires": 60},  # La tarea expira a los 60 segundos si no se ejecuta
    },
}
