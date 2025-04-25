import json
import logging
import time
from typing import Dict, Any, Optional
import requests
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from django_celery_beat.models import PeriodicTask, IntervalSchedule
from django.contrib.auth import get_user_model
from django.db import transaction

from .models import LiveFixtureTask, LiveOddsTask, LiveFixtureData, LiveOddsData, LiveOddsCategory, LiveOddsValue

logger = logging.getLogger(__name__)
User = get_user_model()

def register_periodic_live_tasks() -> Dict[str, Any]:
    """
    Registra las tareas periódicas para actualizar datos de fútbol en vivo
    
    Returns:
        Diccionario con información sobre la configuración de las tareas
    """
    try:
        # Configuración desde settings (o valores por defecto)
        config = {
            'monitor_interval': getattr(settings, 'MONITOR_INTERVAL'),
            'fixture_interval': getattr(settings, 'LIVE_FIXTURES_INTERVAL'),
            'odds_interval': getattr(settings, 'LIVE_ODDS_INTERVAL'), 
        }
        
        # Obtener o crear un usuario para asignar como creador de las tareas
        # Por defecto, usar el primer superusuario o usuario staff que encontremos
        admin_user = User.objects.filter(is_superuser=True).first() or User.objects.filter(is_staff=True).first()
        
        if not admin_user:
            # Si no hay superusuarios o usuarios staff, intentar crear un usuario del sistema
            admin_user, created = User.objects.get_or_create(
                username='system',
                defaults={
                    'is_staff': True,
                    'email': 'system@example.com',
                    'first_name': 'System',
                    'last_name': 'User'
                }
            )
            
            if created:
                # Establecer contraseña aleatoria segura
                admin_user.set_password(User.objects.make_random_password())
                admin_user.save()
                logger.info("Se ha creado un usuario del sistema para las tareas automáticas")
        
        # Registrar o actualizar programación para el monitor de tareas
        monitor_schedule, _ = IntervalSchedule.objects.get_or_create(
            every=config['monitor_interval'],
            period=IntervalSchedule.SECONDS,
        )
        
        # Crear o actualizar la tarea periódica en django-celery-beat
        monitor_task, created = PeriodicTask.objects.update_or_create(
            name='Monitor de tareas en vivo de fútbol',
            defaults={
                'task': 'deep90_app.apps.sports_data.live_tasks.schedule_live_tasks',
                'interval': monitor_schedule,
                'enabled': True,
            }
        )
        
        # Registrar o actualizar la tarea para verificar tareas bloqueadas
        stalled_schedule, _ = IntervalSchedule.objects.get_or_create(
            every=config['monitor_interval'] * 5,  # 5 veces menos frecuente que el monitor principal
            period=IntervalSchedule.SECONDS,
        )
        
        stalled_task, created = PeriodicTask.objects.update_or_create(
            name='Verificador de tareas en vivo bloqueadas',
            defaults={
                'task': 'deep90_app.apps.sports_data.live_tasks.check_and_reset_stalled_tasks',
                'interval': stalled_schedule,
                'enabled': True,
            }
        )
        
        # Asegurar que exista al menos una tarea de fixture en vivo
        # Si ya existe una tarea con este nombre, la actualiza en lugar de crear una nueva
        default_fixture_task, created = LiveFixtureTask.objects.update_or_create(
            name='Actualización de partidos en vivo',
            defaults={
                'interval_seconds': config['fixture_interval'],
                'is_enabled': True,
                'next_run': timezone.now(),
                'created_by': admin_user,  # Asignar el usuario administrador/sistema
                'description': 'Tarea para actualizar datos de partidos en vivo. Creada automáticamente por el sistema.'
            }
        )
        
        # Asegurar que exista al menos una tarea de odds en vivo
        # Si ya existe una tarea con este nombre, la actualiza en lugar de crear una nueva
        default_odds_task, created = LiveOddsTask.objects.update_or_create(
            name='Actualización de cuotas en vivo',
            defaults={
                'interval_seconds': config['odds_interval'],
                'is_enabled': True,
                'next_run': timezone.now(),
                'created_by': admin_user,  # Asignar el usuario administrador/sistema
                'description': 'Tarea para actualizar datos de cuotas en vivo. Creada automáticamente por el sistema.'
            }
        )
        
        return {
            'success': True,
            'config': config,
            'monitor_task_id': monitor_task.id,
            'fixture_task_id': default_fixture_task.id,
            'odds_task_id': default_odds_task.id,
        }
        
    except Exception as e:
        logger.error(f"Error al registrar tareas periódicas de live football: {str(e)}")
        raise


def monitor_live_tasks() -> Dict[str, Any]:
    """
    Ejecuta el monitor de tareas periódicas para actualizar datos de fútbol en vivo
    
    Returns:
        Diccionario con información sobre las tareas ejecutadas
    """
    result = schedule_live_tasks()
    return result


def toggle_task_status(task_type: str, task_id: int) -> Dict[str, Any]:
    """
    Activa o desactiva una tarea de datos en vivo
    
    Args:
        task_type: Tipo de tarea ('fixture' o 'odds')
        task_id: ID de la tarea
        
    Returns:
        Diccionario con información sobre el resultado de la operación
    """
    try:
        if task_type == 'fixture':
            task = LiveFixtureTask.objects.get(id=task_id)
        elif task_type == 'odds':
            task = LiveOddsTask.objects.get(id=task_id)
        else:
            return {'success': False, 'message': f'Tipo de tarea no válido: {task_type}'}
        
        # Cambiar estado
        task.is_enabled = not task.is_enabled
        
        # Si estaba fallida y se está habilitando, reiniciar errores
        if task.status == 'failed' and task.is_enabled:
            task.reset_errors()
            task.status = 'idle'
        
        task.save()
        
        status_text = "habilitada" if task.is_enabled else "deshabilitada"
        return {'success': True, 'message': f'Tarea {task.name} {status_text} correctamente'}
        
    except (LiveFixtureTask.DoesNotExist, LiveOddsTask.DoesNotExist):
        return {'success': False, 'message': f'No se encontró la tarea de tipo {task_type} con ID {task_id}'}
    except Exception as e:
        logger.error(f"Error al cambiar estado de tarea: {str(e)}")
        return {'success': False, 'message': f'Error al procesar la solicitud: {str(e)}'}


def restart_task(task_type: str, task_id: int) -> Dict[str, Any]:
    """
    Reinicia una tarea fallida
    
    Args:
        task_type: Tipo de tarea ('fixture' o 'odds')
        task_id: ID de la tarea
        
    Returns:
        Diccionario con información sobre el resultado de la operación
    """
    try:
        if task_type == 'fixture':
            task = LiveFixtureTask.objects.get(id=task_id)
        elif task_type == 'odds':
            task = LiveOddsTask.objects.get(id=task_id)
        else:
            return {'success': False, 'message': f'Tipo de tarea no válido: {task_type}'}
        
        # Solo permitir reiniciar tareas fallidas
        if task.status != 'failed':
            return {'success': False, 'message': 'Solo se pueden reiniciar tareas con error'}
        
        # Reiniciar estado
        task.reset_errors()
        task.status = 'idle'
        task.next_run = timezone.now()  # Programar para ejecución inmediata
        task.save()
        
        return {'success': True, 'message': f'Tarea {task.name} reiniciada correctamente'}
        
    except (LiveFixtureTask.DoesNotExist, LiveOddsTask.DoesNotExist):
        return {'success': False, 'message': f'No se encontró la tarea de tipo {task_type} con ID {task_id}'}
    except Exception as e:
        logger.error(f"Error al reiniciar tarea: {str(e)}")
        return {'success': False, 'message': f'Error al procesar la solicitud: {str(e)}'}


def reset_stalled_tasks(task_type: str = None, task_id: int = None) -> Dict[str, Any]:
    """
    Verifica y corrige tareas que tienen next_run programado en el pasado
    pero no se están ejecutando por algún error en el servidor.
    
    Args:
        task_type: Tipo de tarea ('fixture', 'odds' o None para ambos)
        task_id: ID específico de una tarea (opcional)
        
    Returns:
        Diccionario con información sobre el resultado de la operación
    """
    now = timezone.now()
    tasks_reset = 0
    tasks_found = 0
    
    try:
        # Crear las consultas base para cada tipo de tarea
        fixture_query = LiveFixtureTask.objects.filter(
            is_enabled=True,
            next_run__lt=now  # Tareas cuya próxima ejecución está en el pasado
        ).exclude(status='running')
        
        odds_query = LiveOddsTask.objects.filter(
            is_enabled=True,
            next_run__lt=now  # Tareas cuya próxima ejecución está en el pasado
        ).exclude(status='running')
        
        # Aplicar filtro por ID si se proporciona
        if task_id is not None:
            if task_type == 'fixture':
                fixture_query = fixture_query.filter(id=task_id)
                odds_query = LiveOddsTask.objects.none()
            elif task_type == 'odds':
                odds_query = odds_query.filter(id=task_id)
                fixture_query = LiveFixtureTask.objects.none()
            else:
                # Si hay ID pero no tipo, intentamos buscar en ambos
                fixture_query = fixture_query.filter(id=task_id)
                odds_query = odds_query.filter(id=task_id)
        elif task_type == 'fixture':
            odds_query = LiveOddsTask.objects.none()
        elif task_type == 'odds':
            fixture_query = LiveFixtureTask.objects.none()
        
        # Procesar tareas de fixture
        for task in fixture_query:
            tasks_found += 1
            # Reiniciar la programación: establecer next_run a ahora
            task.next_run = now
            
            # Si estaba en estado fallido, reiniciarla completamente
            if task.status == 'failed':
                task.reset_errors()
                task.status = 'idle'
            
            task.save(update_fields=['next_run', 'status', 'error_count', 'last_error'])
            tasks_reset += 1
            
            logger.info(f"Tarea de fixture {task.id} ({task.name}) reprogramada para ejecución inmediata")
        
        # Procesar tareas de odds
        for task in odds_query:
            tasks_found += 1
            # Reiniciar la programación: establecer next_run a ahora
            task.next_run = now
            
            # Si estaba en estado fallido, reiniciarla completamente
            if task.status == 'failed':
                task.reset_errors()
                task.status = 'idle'
            
            task.save(update_fields=['next_run', 'status', 'error_count', 'last_error'])
            tasks_reset += 1
            
            logger.info(f"Tarea de odds {task.id} ({task.name}) reprogramada para ejecución inmediata")
        
        # Preparar mensaje de resultado
        result_message = f"{tasks_reset} tareas reprogramadas para ejecución inmediata"
        if task_type:
            result_message += f" (tipo: {task_type})"
        if task_id:
            result_message += f" (ID: {task_id})"
        
        return {
            'success': True,
            'tasks_found': tasks_found,
            'tasks_reset': tasks_reset,
            'message': result_message
        }
        
    except Exception as e:
        logger.error(f"Error al reiniciar tareas con programación incorrecta: {str(e)}")
        return {
            'success': False,
            'tasks_found': tasks_found,
            'tasks_reset': tasks_reset,
            'message': f'Error al procesar la solicitud: {str(e)}'
        }


def clean_invalid_periodic_tasks():
    """
    Elimina tareas periódicas de django-celery-beat que tengan como task
    'deep90_app.apps.sports_data.live_tasks.monitor_live_tasks', ya que no es una tarea Celery válida.
    """
    deleted, _ = PeriodicTask.objects.filter(task='deep90_app.apps.sports_data.live_tasks.monitor_live_tasks').delete()
    logger.info(f"Eliminadas {deleted} tareas periódicas inválidas de monitor_live_tasks")
    return deleted


@shared_task
def check_and_reset_stalled_tasks() -> Dict[str, Any]:
    """
    Tarea programada que verifica periódicamente si hay tareas con next_run en el pasado
    y las reprograma para ejecución inmediata
    
    Returns:
        Diccionario con información sobre la ejecución de la tarea
    """
    logger.info("Verificando tareas con programación incorrecta...")
    return reset_stalled_tasks()


@shared_task
def update_live_fixtures(task_id: int) -> Dict[str, Any]:
    """
    Tarea para actualizar datos de partidos en vivo
    
    Args:
        task_id: ID de la tarea LiveFixtureTask
        
    Returns:
        Diccionario con información sobre la ejecución de la tarea
    """
    start_time = time.time()
    try:
        # Obtener la tarea
        task = LiveFixtureTask.objects.get(id=task_id)
        
        # Verificar si la tarea está habilitada
        if not task.is_enabled:
            return {
                'task_id': task_id,
                'success': True,
                'message': 'Tarea deshabilitada, no se ejecutará',
                'fixtures_updated': 0
            }
        
        # Actualizar estado
        task.status = 'running'
        task.last_run = timezone.now()
        task.save(update_fields=['status', 'last_run'])
        
        # Prepara los headers para la API
        headers = {
            'x-rapidapi-host': 'v3.football.api-sports.io',
            'x-rapidapi-key': settings.API_FOOTBALL_KEY,
        }
        
        # Construir URL para obtener partidos en vivo
        url = f"{settings.API_SPORTS_BASE_URL.rstrip('/')}/fixtures"
        
        # Parámetros para obtener solo partidos en vivo
        params = {'live': 'all'}
        
        # Realizar la llamada a la API
        response = requests.get(
            url=url,
            headers=headers,
            params=params,
            timeout=30
        )
        
        # Verificar respuesta
        if response.status_code != 200:
            raise Exception(f"Error en la API: {response.status_code} - {response.text}")
        
        # Procesar datos recibidos
        data = response.json()
        
        # Contabilizar actualizaciones
        fixtures_updated = 0
        fixtures_total = len(data.get('response', []))
        
        # Extraer IDs de fixtures actualmente en vivo
        current_fixture_ids = [fixture_data['fixture']['id'] for fixture_data in data.get('response', [])]
        
        # Eliminamos TODOS los datos de partidos de esta tarea
        # Esta es la modificación para no mantener históricos
        with transaction.atomic():
            deleted_count = LiveFixtureData.objects.filter(task=task).delete()[0]
            logger.info(f"Eliminados {deleted_count} registros de partidos antiguos para la tarea {task.id}")
        
        # Procesar los fixtures recibidos
        for fixture_data in data.get('response', []):
            fixture_id = fixture_data['fixture']['id']
            
            # Crear el registro de fixture (ya no usamos update_or_create porque hemos borrado todo)
            fixture = LiveFixtureData.objects.create(
                task=task,
                fixture_id=fixture_id,
                date=fixture_data['fixture'].get('date'),
                timestamp=fixture_data['fixture'].get('timestamp'),
                timezone=fixture_data['fixture'].get('timezone'),
                status_long=fixture_data['fixture']['status'].get('long'),
                status_short=fixture_data['fixture']['status'].get('short'),
                elapsed=fixture_data['fixture']['status'].get('elapsed'),
                elapsed_seconds=fixture_data['fixture']['status'].get('elapsed_seconds'),
                venue_name=fixture_data['fixture'].get('venue', {}).get('name'),
                venue_city=fixture_data['fixture'].get('venue', {}).get('city'),
                referee=fixture_data['fixture'].get('referee'),
                
                # Equipos
                home_team_id=fixture_data['teams']['home'].get('id'),
                home_team_name=fixture_data['teams']['home'].get('name'),
                home_team_logo=fixture_data['teams']['home'].get('logo'),
                home_team_winner=fixture_data['teams']['home'].get('winner'),
                
                away_team_id=fixture_data['teams']['away'].get('id'),
                away_team_name=fixture_data['teams']['away'].get('name'),
                away_team_logo=fixture_data['teams']['away'].get('logo'),
                away_team_winner=fixture_data['teams']['away'].get('winner'),
                
                # Goles
                home_goals=fixture_data['goals'].get('home'),
                away_goals=fixture_data['goals'].get('away'),
                
                # Información detallada de puntuación
                home_halftime=fixture_data.get('score', {}).get('halftime', {}).get('home'),
                away_halftime=fixture_data.get('score', {}).get('halftime', {}).get('away'),
                home_fulltime=fixture_data.get('score', {}).get('fulltime', {}).get('home'),
                away_fulltime=fixture_data.get('score', {}).get('fulltime', {}).get('away'),
                home_extratime=fixture_data.get('score', {}).get('extratime', {}).get('home'),
                away_extratime=fixture_data.get('score', {}).get('extratime', {}).get('away'),
                home_penalty=fixture_data.get('score', {}).get('penalty', {}).get('home'),
                away_penalty=fixture_data.get('score', {}).get('penalty', {}).get('away'),
                
                # Liga
                league_id=fixture_data['league'].get('id'),
                league_name=fixture_data['league'].get('name'),
                league_country=fixture_data['league'].get('country'),
                league_logo=fixture_data['league'].get('logo'),
                league_flag=fixture_data['league'].get('flag'),
                league_season=fixture_data['league'].get('season'),
                league_round=fixture_data['league'].get('round'),
                
                # Datos completos
                raw_data=fixture_data,
            )
            fixtures_updated += 1
        
        # Actualizar estado de la tarea
        execution_time = time.time() - start_time
        task.status = 'idle'
        task.next_run = timezone.now() + timezone.timedelta(seconds=task.interval_seconds)
        task.save(update_fields=['status', 'next_run'])
        
        return {
            'task_id': task_id,
            'success': True,
            'fixtures_total': fixtures_total,
            'fixtures_updated': fixtures_updated,
            'execution_time': round(execution_time, 2)
        }
        
    except LiveFixtureTask.DoesNotExist:
        return {
            'task_id': task_id,
            'success': False,
            'error': f"No existe la tarea con ID {task_id}"
        }
    except Exception as e:
        logger.error(f"Error actualizando partidos en vivo: {str(e)}")
        
        try:
            # Intentar actualizar el estado de la tarea
            task = LiveFixtureTask.objects.get(id=task_id)
            task.update_status('failed', error=str(e))
            
            # Programar próxima ejecución si está habilitada
            if task.is_enabled:
                task.next_run = timezone.now() + timezone.timedelta(seconds=task.interval_seconds)
                task.save(update_fields=['next_run'])
        except Exception as inner_e:
            logger.error(f"Error al actualizar estado de tarea: {str(inner_e)}")
        
        return {
            'task_id': task_id,
            'success': False,
            'error': str(e)
        }


@shared_task
def update_live_odds(task_id: int) -> Dict[str, Any]:
    """
    Tarea para actualizar cuotas de partidos en vivo
    
    Args:
        task_id: ID de la tarea LiveOddsTask
        
    Returns:
        Diccionario con información sobre la ejecución de la tarea
    """
    start_time = time.time()
    try:
        # Obtener la tarea
        task = LiveOddsTask.objects.get(id=task_id)
        
        # Verificar si la tarea está habilitada
        if not task.is_enabled:
            return {
                'task_id': task_id,
                'success': True,
                'message': 'Tarea deshabilitada, no se ejecutará',
                'odds_updated': 0
            }
        
        # Actualizar estado
        task.status = 'running'
        task.last_run = timezone.now()
        task.save(update_fields=['status', 'last_run'])
        
        # Prepara los headers para la API
        headers = {
            'x-rapidapi-host': 'v3.football.api-sports.io',
            'x-rapidapi-key': settings.API_FOOTBALL_KEY,
        }
        
        # Obtener los IDs de partidos en vivo actuales
        live_fixtures = LiveFixtureData.objects.filter(
            status_short__in=['1H', '2H', 'HT', 'ET', 'BT', 'P', 'INT']
        ).values_list('fixture_id', flat=True)
        
        if not live_fixtures:
            logger.info("No hay partidos en vivo para obtener cuotas")
            task.status = 'idle'
            task.next_run = timezone.now() + timezone.timedelta(seconds=task.interval_seconds)
            task.save(update_fields=['status', 'next_run'])
            return {
                'task_id': task_id,
                'success': True,
                'message': 'No hay partidos en vivo',
                'odds_updated': 0
            }
        
        # Construir URL para obtener cuotas
        url = f"{settings.API_SPORTS_BASE_URL.rstrip('/')}/odds/live"
        
        # Realizar la llamada a la API
        response = requests.get(
            url=url,
            headers=headers,
            timeout=30
        )
        
        # Verificar respuesta
        if response.status_code != 200:
            raise Exception(f"Error en la API: {response.status_code} - {response.text}")
        
        # Procesar datos recibidos
        data = response.json()
        
        # Contabilizar actualizaciones
        odds_updated = 0
        odds_total = len(data.get('response', []))
        categories_updated = 0
        values_updated = 0
        
        # Eliminar TODOS los datos de cuotas relacionados con esta tarea
        # Esto elimina todas las LiveOddsData asociadas a la tarea, lo que también elimina
        # en cascada todas las categorías y valores debido a la relación
        with transaction.atomic():
            deleted_count = LiveOddsData.objects.filter(task=task).delete()[0]
            logger.info(f"Eliminados {deleted_count} registros de cuotas y sus categorías/valores para la tarea {task.id}")
        
        # Procesar las cuotas recibidas
        for odds_data in data.get('response', []):
            fixture_id = odds_data['fixture']['id']
            
            # Solo procesar partidos que nos interesan
            if fixture_id not in live_fixtures:
                continue
            
            # Datos principales
            league = odds_data.get('league', {})
            fixture = odds_data.get('fixture', {})
            
            # Crear el registro de cuotas (ya no usamos update_or_create porque hemos borrado todo)
            odds = LiveOddsData.objects.create(
                task=task,
                fixture_id=fixture_id,
                league_id=league.get('id'),
                league_season=league.get('season'),
                
                # Equipos y goles
                home_team_id=odds_data.get('teams', {}).get('home', {}).get('id'),
                away_team_id=odds_data.get('teams', {}).get('away', {}).get('id'),
                home_goals=odds_data.get('goals', {}).get('home'),
                away_goals=odds_data.get('goals', {}).get('away'),
                
                # Estado
                status_elapsed=fixture.get('status', {}).get('elapsed'),
                status_elapsed_seconds=fixture.get('status', {}).get('elapsed_seconds'),
                status_long=fixture.get('status', {}).get('long'),
                
                # Estado de las apuestas
                is_blocked=fixture.get('status', {}).get('short') in ['INT', 'SUSP', 'PST', 'CANC', 'ABD'],
                is_stopped=fixture.get('status', {}).get('short') in ['HT', 'BT'],
                is_finished=fixture.get('status', {}).get('short') in ['FT', 'AET', 'PEN', 'WO', 'AWD'],
                
                # Datos brutos y tiempo
                update_time=odds_data.get('update'),
                raw_odds_data=odds_data,  # Guardar solo los datos de este partido, no toda la respuesta
            )
            odds_updated += 1
            
            logger.info(f"Procesando cuotas para partido {fixture_id}")
            
            # Procesar categorías y valores de cuotas detalladas
            try:
                # Ya no necesitamos eliminar las categorías anteriores porque hemos eliminado todo el registro de LiveOddsData
                # Procesar las nuevas categorías y valores
                if 'odds' in odds_data and isinstance(odds_data['odds'], list):
                    logger.info(f"Encontradas {len(odds_data['odds'])} categorías de cuotas para el partido {fixture_id}")
                    
                    for odds_category in odds_data['odds']:
                        category_id = odds_category.get('id')
                        category_name = odds_category.get('name')
                        
                        if not category_id or not category_name:
                            logger.warning(f"Categoría de cuotas sin ID o nombre: {odds_category}")
                            continue
                        
                        # Crear la nueva categoría
                        category = LiveOddsCategory.objects.create(
                            odds_data=odds,
                            category_id=category_id,
                            name=category_name
                        )
                        categories_updated += 1
                        
                        # Verificar que haya valores para esta categoría
                        if 'values' not in odds_category or not isinstance(odds_category['values'], list):
                            logger.warning(f"Categoría {category_name} sin valores o formato incorrecto")
                            continue
                            
                        # Procesar los valores para esta categoría
                        for value_data in odds_category['values']:
                            # Verificar si hay datos de handicap
                            handicap = value_data.get('handicap')
                            
                            # Convertir 'main' a booleano si existe
                            main_value = value_data.get('main')
                            if main_value is not None:
                                if isinstance(main_value, str):
                                    main_value = main_value.lower() == 'true'
                                else:
                                    main_value = bool(main_value)
                            
                            # Crear el valor
                            LiveOddsValue.objects.create(
                                category=category,
                                value=value_data.get('value', ''),
                                odd=value_data.get('odd', '0'),
                                handicap=handicap,
                                main=main_value,
                                suspended=value_data.get('suspended', False)
                            )
                            values_updated += 1
                else:
                    logger.warning(f"No se encontraron datos de cuotas para el partido {fixture_id} o formato incorrecto")
            except Exception as e:
                logger.error(f"Error procesando categorías y valores para el partido {fixture_id}: {str(e)}")
                # Permitimos que el proceso continúe con otros partidos
        
        # Actualizar estado de la tarea
        execution_time = time.time() - start_time
        task.status = 'idle'
        task.next_run = timezone.now() + timezone.timedelta(seconds=task.interval_seconds)
        task.save(update_fields=['status', 'next_run'])
        
        return {
            'task_id': task_id,
            'success': True,
            'odds_total': odds_total,
            'odds_updated': odds_updated,
            'categories_updated': categories_updated,
            'values_updated': values_updated,
            'execution_time': round(execution_time, 2)
        }
        
    except LiveOddsTask.DoesNotExist:
        return {
            'task_id': task_id,
            'success': False,
            'error': f"No existe la tarea con ID {task_id}"
        }
    except Exception as e:
        logger.error(f"Error actualizando cuotas en vivo: {str(e)}")
        
        try:
            # Intentar actualizar el estado de la tarea
            task = LiveOddsTask.objects.get(id=task_id)
            task.update_status('failed', error=str(e))
            
            # Programar próxima ejecución si está habilitada
            if task.is_enabled:
                task.next_run = timezone.now() + timezone.timedelta(seconds=task.interval_seconds)
                task.save(update_fields=['next_run'])
        except Exception as inner_e:
            logger.error(f"Error al actualizar estado de tarea: {str(inner_e)}")
        
        return {
            'task_id': task_id,
            'success': False,
            'error': str(e)
        }


@shared_task
def schedule_live_tasks():
    """
    Comprueba qué tareas de datos en vivo deben ejecutarse y las programa
    """
    now = timezone.now()
    
    # Programar tareas de partidos en vivo
    fixture_tasks = LiveFixtureTask.objects.filter(
        is_enabled=True,
        next_run__lte=now
    ).exclude(status='running')
    
    for task in fixture_tasks:
        logger.info(f"Programando actualización de partidos en vivo para tarea: {task.id} - {task.name}")
        update_live_fixtures.delay(task_id=task.id)
    
    # Programar tareas de cuotas en vivo
    odds_tasks = LiveOddsTask.objects.filter(
        is_enabled=True,
        next_run__lte=now
    ).exclude(status='running')
    
    for task in odds_tasks:
        logger.info(f"Programando actualización de cuotas en vivo para tarea: {task.id} - {task.name}")
        update_live_odds.delay(task_id=task.id)
        
    return {
        'fixture_tasks_scheduled': fixture_tasks.count(),
        'odds_tasks_scheduled': odds_tasks.count(),
        'timestamp': now.isoformat()
    }