import time
import logging
import requests
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from .models import LiveFixtureData, LiveFixtureTask, LiveOddsData, LiveOddsTask

logger = logging.getLogger(__name__)


class LiveAPIService:
    """
    Servicio para obtener datos en vivo de la API de fútbol.
    Esta clase maneja las llamadas a la API y el procesamiento de datos para mantener
    actualizados los partidos en vivo y sus cuotas.
    """
    
    @staticmethod
    def fetch_live_fixtures(task):
        """
        Obtiene los partidos en vivo desde la API.
        
        Args:
            task: Objeto LiveFixtureTask que define la tarea de obtención de partidos
            
        Returns:
            dict: Resultado de la operación con información de éxito y errores
        """
        start_time = time.time()

        logger.info(f"Ejecutando tarea de partidos en vivo: {task}")
        
        try:
            # Actualizar estado de la tarea
            task.update_status('running')
            task.last_run = timezone.now()
            task.save(update_fields=['last_run'])
            
            # Preparar headers para la API
            headers = {
                'x-rapidapi-host': 'v3.football.api-sports.io',
                'x-rapidapi-key': settings.API_FOOTBALL_KEY,
            }
            
            # Construir la URL para partidos en vivo
            url = f"{settings.API_SPORTS_BASE_URL.rstrip('/')}/fixtures"
            
            # Parámetros para la petición
            params = {
                'live': 'all'  # Obtener todos los partidos en vivo
            }
            
            # Realizar la petición HTTP
            response = requests.get(
                url=url,
                headers=headers,
                params=params,
                timeout=30
            )
            
            # Calcular el tiempo de ejecución
            execution_time = time.time() - start_time
            
            # Verificar respuesta
            if response.status_code == 200:
                data = response.json()
                
                # Procesar los datos obtenidos
                success = LiveAPIService._process_live_fixtures(task, data)
                
                # Calcular próxima ejecución
                task.next_run = timezone.now() + timedelta(seconds=task.interval_seconds)
                task.update_status('idle')
                task.save(update_fields=['next_run'])
                
                logger.info(f"Tarea de partidos en vivo completada. Tiempo: {execution_time:.2f}s. Próxima ejecución: {task.next_run}")
                
                return {
                    'success': success,
                    'execution_time': execution_time,
                    'message': f"Se obtuvieron datos de {len(data.get('response', []))} partidos en vivo"
                }
            else:
                # Manejar error en la respuesta
                error_msg = f"Error al obtener partidos en vivo. Código: {response.status_code}, Respuesta: {response.text}"
                logger.error(error_msg)
                
                # Calcular próxima ejecución con penalización por error
                task.next_run = timezone.now() + timedelta(seconds=task.interval_seconds * (1 + min(5, task.error_count)))
                task.update_status('failed', error=error_msg)
                task.save(update_fields=['next_run'])
                
                return {
                    'success': False,
                    'execution_time': execution_time,
                    'message': error_msg
                }
                
        except Exception as e:
            # Capturar y registrar cualquier excepción
            execution_time = time.time() - start_time
            error_msg = f"Excepción al obtener partidos en vivo: {str(e)}"
            logger.exception(error_msg)
            
            # Actualizar estado con el error
            task.next_run = timezone.now() + timedelta(seconds=task.interval_seconds * (1 + min(5, task.error_count)))
            task.update_status('failed', error=error_msg)
            task.save(update_fields=['next_run'])
            
            return {
                'success': False,
                'execution_time': execution_time,
                'message': error_msg
            }
    
    @staticmethod
    def _process_live_fixtures(task, data):
        """
        Procesa los datos de partidos en vivo y los almacena en la base de datos.
        
        Args:
            task: Objeto LiveFixtureTask que define la tarea
            data: Datos obtenidos de la API
            
        Returns:
            bool: True si el procesamiento fue exitoso, False en caso contrario
        """
        try:
            # Verificar si la respuesta tiene datos válidos
            fixtures_data = data.get('response', [])
            
            if not fixtures_data:
                logger.warning("No hay partidos en vivo actualmente")
                # Eliminar todos los partidos existentes ya que no hay ninguno en vivo
                LiveFixtureData.objects.filter(task=task).delete()
                return True
            
            # Obtener IDs de los partidos en la respuesta
            current_fixture_ids = [fixture.get('fixture', {}).get('id') for fixture in fixtures_data if fixture.get('fixture', {}).get('id')]
            
            # Eliminar partidos que ya no están en vivo
            LiveFixtureData.objects.filter(task=task).exclude(fixture_id__in=current_fixture_ids).delete()
            
            # Procesar y actualizar/crear datos de partidos en vivo
            for fixture_data in fixtures_data:
                fixture = fixture_data.get('fixture', {})
                teams = fixture_data.get('teams', {})
                goals = fixture_data.get('goals', {})
                score = fixture_data.get('score', {})
                league = fixture_data.get('league', {})
                
                fixture_id = fixture.get('id')
                
                if not fixture_id:
                    continue  # Saltar si no hay ID de partido
                
                # Parsear la fecha a un objeto datetime
                date_str = fixture.get('date')
                try:
                    date = datetime.fromisoformat(date_str.replace('Z', '+00:00')) if date_str else None
                except (ValueError, AttributeError):
                    date = None
                
                # Buscar si ya existe el partido o crear uno nuevo
                live_fixture, created = LiveFixtureData.objects.update_or_create(
                    task=task,
                    fixture_id=fixture_id,
                    defaults={
                        'date': date,
                        'timestamp': fixture.get('timestamp', 0),
                        'timezone': fixture.get('timezone', 'UTC'),
                        'referee': fixture.get('referee'),
                        'status_long': fixture.get('status', {}).get('long', ''),
                        'status_short': fixture.get('status', {}).get('short', ''),
                        'elapsed': fixture.get('status', {}).get('elapsed'),
                        'elapsed_seconds': fixture.get('status', {}).get('seconds'),
                        'venue_name': fixture.get('venue', {}).get('name'),
                        'venue_city': fixture.get('venue', {}).get('city'),
                        
                        'home_team_id': teams.get('home', {}).get('id', 0),
                        'home_team_name': teams.get('home', {}).get('name', ''),
                        'home_team_logo': teams.get('home', {}).get('logo'),
                        'home_team_winner': teams.get('home', {}).get('winner'),
                        
                        'away_team_id': teams.get('away', {}).get('id', 0),
                        'away_team_name': teams.get('away', {}).get('name', ''),
                        'away_team_logo': teams.get('away', {}).get('logo'),
                        'away_team_winner': teams.get('away', {}).get('winner'),
                        
                        'home_goals': goals.get('home'),
                        'away_goals': goals.get('away'),
                        
                        'home_halftime': score.get('halftime', {}).get('home'),
                        'away_halftime': score.get('halftime', {}).get('away'),
                        'home_fulltime': score.get('fulltime', {}).get('home'),
                        'away_fulltime': score.get('fulltime', {}).get('away'),
                        'home_extratime': score.get('extratime', {}).get('home'),
                        'away_extratime': score.get('extratime', {}).get('away'),
                        'home_penalty': score.get('penalty', {}).get('home'),
                        'away_penalty': score.get('penalty', {}).get('away'),
                        
                        'league_id': league.get('id', 0),
                        'league_name': league.get('name', ''),
                        'league_country': league.get('country', ''),
                        'league_logo': league.get('logo'),
                        'league_flag': league.get('flag'),
                        'league_season': league.get('season', 0),
                        'league_round': league.get('round', ''),
                        
                        'raw_data': fixture_data
                    }
                )
                
                if created:
                    logger.info(f"Nuevo partido en vivo añadido: {live_fixture}")
                else:
                    logger.debug(f"Partido en vivo actualizado: {live_fixture}")
            
            return True
            
        except Exception as e:
            logger.exception(f"Error procesando partidos en vivo: {e}")
            return False
    
    @staticmethod
    def fetch_live_odds(task):
        """
        Obtiene las cuotas en vivo desde la API.
        
        Args:
            task: Objeto LiveOddsTask que define la tarea de obtención de cuotas
            
        Returns:
            dict: Resultado de la operación con información de éxito y errores
        """
        start_time = time.time()
        
        try:
            # Actualizar estado de la tarea
            task.update_status('running')
            task.last_run = timezone.now()
            task.save(update_fields=['last_run'])
            
            # Preparar headers para la API
            headers = {
                'x-rapidapi-host': 'v3.football.api-sports.io',
                'x-rapidapi-key': settings.API_FOOTBALL_KEY,
            }
            
            # Construir la URL para cuotas en vivo
            url = f"{settings.API_SPORTS_BASE_URL.rstrip('/')}/odds/live"
            
            # Realizar la petición HTTP
            response = requests.get(
                url=url,
                headers=headers,
                timeout=30
            )
            
            # Calcular el tiempo de ejecución
            execution_time = time.time() - start_time
            
            # Verificar respuesta
            if response.status_code == 200:
                data = response.json()
                
                # Procesar los datos obtenidos
                success = LiveAPIService._process_live_odds(task, data)
                
                # Calcular próxima ejecución
                task.next_run = timezone.now() + timedelta(seconds=task.interval_seconds)
                task.update_status('idle')
                task.save(update_fields=['next_run'])
                
                logger.info(f"Tarea de cuotas en vivo completada. Tiempo: {execution_time:.2f}s. Próxima ejecución: {task.next_run}")
                
                return {
                    'success': success,
                    'execution_time': execution_time,
                    'message': f"Se obtuvieron datos de {len(data.get('response', []))} cuotas en vivo"
                }
            else:
                # Manejar error en la respuesta
                error_msg = f"Error al obtener cuotas en vivo. Código: {response.status_code}, Respuesta: {response.text}"
                logger.error(error_msg)
                
                # Calcular próxima ejecución con penalización por error
                task.next_run = timezone.now() + timedelta(seconds=task.interval_seconds * (1 + min(5, task.error_count)))
                task.update_status('failed', error=error_msg)
                task.save(update_fields=['next_run'])
                
                return {
                    'success': False,
                    'execution_time': execution_time,
                    'message': error_msg
                }
                
        except Exception as e:
            # Capturar y registrar cualquier excepción
            execution_time = time.time() - start_time
            error_msg = f"Excepción al obtener cuotas en vivo: {str(e)}"
            logger.exception(error_msg)
            
            # Actualizar estado con el error
            task.next_run = timezone.now() + timedelta(seconds=task.interval_seconds * (1 + min(5, task.error_count)))
            task.update_status('failed', error=error_msg)
            task.save(update_fields=['next_run'])
            
            return {
                'success': False,
                'execution_time': execution_time,
                'message': error_msg
            }
    
    @staticmethod
    def _process_live_odds(task, data):
        """
        Procesa los datos de cuotas en vivo y los almacena en la base de datos.
        
        Args:
            task: Objeto LiveOddsTask que define la tarea
            data: Datos obtenidos de la API
            
        Returns:
            bool: True si el procesamiento fue exitoso, False en caso contrario
        """
        try:
            # Verificar si la respuesta tiene datos válidos
            odds_data = data.get('response', [])
            
            if not odds_data:
                logger.warning("No hay cuotas en vivo actualmente")
                # Eliminar todas las cuotas existentes ya que no hay ninguna en vivo
                LiveOddsData.objects.filter(task=task).delete()
                return True
            
            # Obtener IDs de los partidos en la respuesta
            current_fixture_ids = [odd.get('fixture', {}).get('id') for odd in odds_data if odd.get('fixture', {}).get('id')]
            
            # Eliminar cuotas que ya no están en vivo
            LiveOddsData.objects.filter(task=task).exclude(fixture_id__in=current_fixture_ids).delete()
            
            # Procesar y actualizar/crear datos de cuotas en vivo
            for odds_item in odds_data:
                fixture = odds_item.get('fixture', {})
                fixture_id = fixture.get('id')
                
                if not fixture_id:
                    continue  # Saltar si no hay ID de partido
                
                # Buscar si ya existe el registro de cuotas o crear uno nuevo
                live_odds, created = LiveOddsData.objects.update_or_create(
                    task=task,
                    fixture_id=fixture_id,
                    defaults={
                        'league_id': odds_item.get('league', {}).get('id', 0),
                        'league_season': odds_item.get('league', {}).get('season', 0),
                        
                        'home_team_id': odds_item.get('teams', {}).get('home', {}).get('id', 0),
                        'away_team_id': odds_item.get('teams', {}).get('away', {}).get('id', 0),
                        'home_goals': odds_item.get('teams', {}).get('home', {}).get('goals'),
                        'away_goals': odds_item.get('teams', {}).get('away', {}).get('goals'),
                        
                        'status_elapsed': fixture.get('status', {}).get('elapsed'),
                        'status_elapsed_seconds': fixture.get('status', {}).get('seconds'),
                        'status_long': fixture.get('status', {}).get('long', ''),
                        
                        'is_stopped': odds_item.get('status', {}).get('stopped', False),
                        'is_blocked': odds_item.get('status', {}).get('blocked', False),
                        'is_finished': odds_item.get('status', {}).get('finished', False),
                        
                        'update_time': odds_item.get('update', ''),
                        'raw_odds_data': odds_item
                    }
                )
                
                if created:
                    logger.info(f"Nuevas cuotas en vivo añadidas: {live_odds}")
                else:
                    logger.debug(f"Cuotas en vivo actualizadas: {live_odds}")
            
            return True
            
        except Exception as e:
            logger.exception(f"Error procesando cuotas en vivo: {e}")
            return False