import json
import time
from typing import Dict, Any, Optional
import requests
from celery import shared_task
from django.conf import settings
from django_celery_beat.models import PeriodicTask, IntervalSchedule

from .models import ScheduledTask, APIResult


@shared_task
def execute_api_request(task_id: int) -> Dict[str, Any]:
    """
    Ejecuta una solicitud a la API de fútbol.
    
    Args:
        task_id: ID de la tarea programada a ejecutar
        
    Returns:
        Diccionario con información sobre la ejecución de la tarea
    """
    start_time = time.time()
    task = ScheduledTask.objects.get(id=task_id)
    
    # Actualiza el estado de la tarea
    task.status = 'running'
    task.save(update_fields=['status'])
    
    try:
        # Prepara los headers para la API
        headers = {
            'x-rapidapi-host': 'v3.football.api-sports.io',
            'x-rapidapi-key': settings.API_FOOTBALL_KEY,
        }
        
        # Construye la URL completa
        url = f"{settings.API_SPORTS_BASE_URL.rstrip('/')}/{task.endpoint.endpoint.lstrip('/')}"
        
        # Realiza la llamada a la API
        response = requests.get(
            url=url,
            headers=headers,
            params=task.parameters if task.parameters else None,
            timeout=30
        )
        
        # Calcula el tiempo de ejecución
        execution_time = time.time() - start_time
        
        # Guarda el resultado
        result = APIResult.objects.create(
            task=task,
            response_code=response.status_code,
            response_data=response.json() if response.status_code == 200 else None,
            execution_time=execution_time,
            success=response.status_code == 200,
            error_message=None if response.status_code == 200 else response.text
        )
        
        # Actualiza el estado de la tarea
        task.status = 'success' if response.status_code == 200 else 'failed'
        task.save(update_fields=['status'])
        
        return {
            'task_id': task_id,
            'result_id': result.id,
            'success': response.status_code == 200,
            'status_code': response.status_code
        }
        
    except Exception as e:
        # Registra el error
        execution_time = time.time() - start_time
        APIResult.objects.create(
            task=task,
            response_code=500,
            response_data=None,
            execution_time=execution_time,
            success=False,
            error_message=str(e)
        )
        
        # Actualiza el estado de la tarea
        task.status = 'failed'
        task.save(update_fields=['status'])
        
        return {
            'task_id': task_id,
            'success': False,
            'error': str(e)
        }


@shared_task
def schedule_periodic_tasks():
    """Revisa y programa tareas periódicas que no tengan una tarea de Celery asociada."""
    periodic_tasks = ScheduledTask.objects.filter(
        schedule_type='periodic',
        periodic_interval__isnull=False,
        celery_task_id__isnull=True
    )
    
    for task in periodic_tasks:
        # Crea un intervalo para la tarea
        schedule, created = IntervalSchedule.objects.get_or_create(
            every=task.periodic_interval,
            period=IntervalSchedule.MINUTES,
        )
        
        # Crea una tarea periódica en Celery
        name = f"sports_data_periodic_task_{task.id}"
        periodic_task = PeriodicTask.objects.create(
            interval=schedule,
            name=name,
            task='deep90_app.apps.sports_data.tasks.execute_api_request',
            kwargs=json.dumps({'task_id': task.id}),
        )
        
        # Guarda el ID de la tarea periódica en la tarea programada
        task.celery_task_id = str(periodic_task.id)
        task.save(update_fields=['celery_task_id'])