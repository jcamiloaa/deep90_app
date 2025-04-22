"""
Módulo para definir y manejar los flujos de WhatsApp para la app de sports_data.

Este módulo contiene las definiciones y lógica para crear los flujos interactivos
que permitirán a los usuarios consultar datos de partidos a través de WhatsApp.
"""

import json
import logging
from django.utils.translation import gettext_lazy as _
from deep90_app.apps.sports_data.models import FixtureData, LeagueData

logger = logging.getLogger(__name__)


def ensure_serializable(obj):
    """
    Asegura que los objetos de traducción sean serializables a JSON.
    Convierte objetos __proxy__ de Django a strings.
    
    Args:
        obj: Objeto a hacer serializable
        
    Returns:
        Objeto serializable a JSON
    """
    if isinstance(obj, dict):
        return {k: ensure_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [ensure_serializable(item) for item in obj]
    elif hasattr(obj, "__proxy__"):  # Detecta objetos de traducción
        return str(obj)
    return obj


class FootballDataFlow:
    """
    Clase para manejar la lógica de flujos de consultas de datos de fútbol.
    Esta clase proporciona métodos para generar pantallas y procesar selecciones del usuario.
    """

    # Definir respuestas para cada pantalla del flujo
    SCREEN_RESPONSES = {
        "WELCOME": {
            "screen": "WELCOME",
            "data": {
                "options": [
                    {"id": "live_results", "title": "Resultados en vivo"}
                ]
            }
        },
        "SELECT_COUNTRY": {
            "screen": "SELECT_COUNTRY",
            "data": {
                "available_countries": []  # Se llenará dinámicamente
            }
        },
        "SELECT_FIXTURE": {
            "screen": "SELECT_FIXTURE",
            "data": {
                "country_name": "",  # Se llenará dinámicamente
                "available_fixtures": []  # Se llenará dinámicamente
            }
        },
        "FIXTURE_DETAIL": {
            "screen": "FIXTURE_DETAIL",
            "data": {
                "fixture_id": 0,  # Se llenará dinámicamente
                "fixture_details": {}  # Se llenará dinámicamente
            }
        },
        "NEXT_STEP": {
            "screen": "NEXT_STEP",
            "data": {
                "fixture_id": 0,  # Se llenará dinámicamente
                "next_actions": []  # Se llenará dinámicamente
            }
        },
        "SUCCESS": {
            "screen": "SUCCESS",
            "data": {
                "extension_message_response": {
                    "params": {
                        "flow_token": "REPLACE_FLOW_TOKEN",  # Se reemplazará con el token real
                        "result": "completed"
                    }
                }
            }
        }
    }

    @classmethod
    def handle_flow_request(cls, decrypted_body):
        """
        Maneja la solicitud del flujo y devuelve la pantalla apropiada según la acción y pantalla actual.
        
        Args:
            decrypted_body: Datos descifrados de la solicitud
            
        Returns:
            dict: La pantalla a mostrar
        """
        screen = decrypted_body.get('screen')
        data = decrypted_body.get('data', {})
        action = decrypted_body.get('action')
        flow_token = decrypted_body.get('flow_token')
        
        logger.debug(f"Manejando solicitud de flujo - Acción: {action}, Pantalla: {screen}, Datos: {data}")
        
        # Manejar la acción de ping (health check)
        if action == 'ping':
            logger.debug("Manejando solicitud de ping (health check)")
            return {
                "data": {
                    "status": "active"
                }
            }
        
        # Manejar notificaciones de error del cliente
        if data and 'error' in data:
            logger.warning(f"Error del cliente recibido: {data['error']}")
            return {
                "data": {
                    "acknowledged": True
                }
            }
        
        # Manejar acción inicial
        if action == 'INIT':
            logger.debug("Manejando acción INIT - Mostrando pantalla de bienvenida")
            logger.info("Iniciando flujo con pantalla de bienvenida")
            return cls._get_welcome_screen()
        
        # Manejar acción de retroceso
        if action == 'BACK':
            logger.debug(f"Manejando acción BACK desde pantalla {screen}")
            if screen == 'SELECT_FIXTURE':
                return cls._get_countries_screen()
            elif screen == 'FIXTURE_DETAIL':
                country_name = data.get('country_name', '')
                return cls._get_fixtures_screen(country_name)
            elif screen == 'SELECT_COUNTRY':
                return cls._get_welcome_screen()
            else:
                return cls._get_welcome_screen()
        
        # Manejar intercambio de datos
        if action == 'data_exchange':
            logger.debug(f"Manejando acción data_exchange en pantalla {screen}")
            
            # Manejar selección según la pantalla actual
            if screen == 'WELCOME':
                # Buscar la opción seleccionada en los datos
                selected_option = cls._extract_from_data(
                    data, 
                    prefix='', 
                    fallback_keys=[
                        'selected_option', 
                        'welcome_form.selected_option',
                        'Selecciona_opcion_b9cdae',
                        'flow_path.Selecciona_opcion_b9cdae'
                    ]
                )
                
                logger.info(f"Opción seleccionada: {selected_option}")
                
                # Con el nuevo formato, la opción seleccionada será "0_Resultados_en_vivo"
                if selected_option == '0_Resultados_en_vivo' or selected_option == 'live_results':
                    logger.debug("Usuario seleccionó resultados en vivo, mostrando países")
                    return cls._get_countries_screen()
                else:
                    # Si no hay una selección válida, volver a la pantalla de bienvenida
                    logger.warning(f"No se encontró una selección válida en la pantalla de bienvenida: {selected_option}")
                    return cls._get_welcome_screen()
                    
            elif screen == 'SELECT_COUNTRY':
                # Buscar la selección del país en múltiples lugares posibles
                selected_country = cls._extract_from_data(data, prefix='country_', fallback_keys=['department', 'selected_country', 'country_form.selected_country'])
                
                logger.info(f"País seleccionado: {selected_country}")
                
                if not selected_country:
                    logger.warning("No se encontró selección de país")
                    return cls._get_countries_screen()
                
                # Procesar el país seleccionado
                if selected_country.startswith('country_'):
                    country = selected_country.replace('country_', '')
                else:
                    country = selected_country
                
                logger.debug(f"País procesado: {country}")
                
                if country:
                    return cls._get_fixtures_screen(country)
                else:
                    logger.warning("No se encontró selección de país después del procesamiento")
                    return cls._get_countries_screen()
                    
            elif screen == 'SELECT_FIXTURE':
                # Buscar la selección de partido en los datos
                selected_fixture = cls._extract_from_data(data, prefix='fixture_', fallback_keys=['department', 'selected_fixture', 'fixture_form.selected_fixture'])
                country_name = data.get('country_name', '')
                
                logger.info(f"Partido seleccionado: {selected_fixture}")
                
                if not selected_fixture:
                    logger.warning("No se encontró selección de partido")
                    return cls._get_fixtures_screen(country_name)
                
                # Procesar el partido seleccionado
                try:
                    if selected_fixture.startswith('fixture_'):
                        fixture_id = int(selected_fixture.replace('fixture_', ''))
                        logger.debug(f"ID de partido extraído: {fixture_id}")
                    else:
                        # Intentar convertir directamente, podría ser solo el número
                        try:
                            fixture_id = int(selected_fixture)
                            logger.debug(f"ID de partido extraído directamente: {fixture_id}")
                        except ValueError:
                            logger.warning(f"No se pudo convertir '{selected_fixture}' a un ID de partido")
                            fixture_id = None
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Error al parsear fixture_id de {selected_fixture}: {str(e)}")
                    fixture_id = None
                
                if fixture_id:
                    return cls._get_fixture_detail_screen(fixture_id)
                else:
                    logger.warning(f"No se encontró ID de partido válido en la selección {selected_fixture}")
                    return cls._get_fixtures_screen(country_name)
                    
            elif screen == 'FIXTURE_DETAIL':
                # Mostrar opciones para los próximos pasos
                fixture_id = data.get('fixture_id', 0)
                return cls._get_next_step_screen(fixture_id)
            
            elif screen == 'NEXT_STEP':
                # Procesar la selección de la siguiente acción
                selected_action = cls._extract_from_data(data, prefix='action_', fallback_keys=['selected_action', 'next_step_form.selected_action'])
                fixture_id = data.get('fixture_id', 0)
                
                logger.info(f"Acción seleccionada: {selected_action}")
                
                if selected_action == 'action_finish':
                    # Completar el flujo cuando se selecciona finalizar
                    logger.debug("Usuario seleccionó finalizar, completando flujo")
                    success_response = dict(cls.SCREEN_RESPONSES["SUCCESS"])
                    success_response["data"]["extension_message_response"]["params"]["flow_token"] = flow_token
                    return success_response
                
                # Aquí se pueden manejar otras acciones como hablar con asistente para predicciones,
                # probabilidades en vivo o apuestas, dependiendo de la integración necesaria
                
                # Por defecto, volver a la pantalla de países
                return cls._get_countries_screen()
        
        # Si no se reconoce la acción o pantalla, volver a la pantalla inicial
        logger.warning(f"Acción no reconocida: {action}, Pantalla: {screen}")
        return cls._get_welcome_screen()
    
    @classmethod
    def _extract_from_data(cls, data, prefix='', fallback_keys=None):
        """
        Extrae un valor de los datos recibidos, buscando en varias ubicaciones posibles.
        
        Args:
            data: Diccionario de datos
            prefix: Prefijo a buscar en valores de strings
            fallback_keys: Lista de claves a revisar en orden de prioridad
            
        Returns:
            str: El valor encontrado o None
        """
        if fallback_keys:
            for key in fallback_keys:
                if '.' in key:
                    parts = key.split('.')
                    if len(parts) == 2 and parts[0] in data and isinstance(data[parts[0]], dict) and parts[1] in data[parts[0]]:
                        value = data[parts[0]][parts[1]]
                        # Manejar si el valor es una lista (nuevo formato)
                        if isinstance(value, list) and len(value) > 0:
                            return value[0]  # Devuelve el primer elemento de la lista
                        return value
                elif key in data:
                    value = data.get(key)
                    # Manejar si el valor es una lista (nuevo formato)
                    if isinstance(value, list) and len(value) > 0:
                        return value[0]  # Devuelve el primer elemento de la lista
                    return value
        
        # Buscar en cualquier clave y valor
        for key, value in data.items():
            # Manejar si el valor es una lista (nuevo formato)
            if isinstance(value, list) and len(value) > 0:
                if not prefix or str(value[0]).startswith(prefix):
                    return value[0]
            elif isinstance(value, str) and (not prefix or value.startswith(prefix)):
                return value
            elif isinstance(value, dict):
                for subkey, subvalue in value.items():
                    # Manejar si el subvalor es una lista (nuevo formato)
                    if isinstance(subvalue, list) and len(subvalue) > 0:
                        if not prefix or str(subvalue[0]).startswith(prefix):
                            return subvalue[0]
                    elif isinstance(subvalue, str) and (not prefix or subvalue.startswith(prefix)):
                        return subvalue
        
        return None
    
    @classmethod
    def _get_welcome_screen(cls):
        """
        Genera la pantalla de bienvenida inicial.
        
        Returns:
            dict: Estructura de la pantalla para WhatsApp Flows.
        """
        logger.debug("Generando pantalla WELCOME")
        
        # Crear una copia de la respuesta base
        screen_response = dict(cls.SCREEN_RESPONSES["WELCOME"])
        
        # Convertir todos los objetos de traducción a strings para que sean serializables
        return ensure_serializable(screen_response)
    
    @classmethod
    def _get_countries_screen(cls):
        """
        Genera la pantalla de selección de países.
        
        Returns:
            dict: Estructura de la pantalla para WhatsApp Flows.
        """
        logger.debug("Generando pantalla SELECT_COUNTRY")
        
        # Obtener países únicos de FixtureData
        countries = FixtureData.objects.values_list('league_country', flat=True).distinct().order_by('league_country')
        
        # Crear una copia de la respuesta base
        screen_response = dict(cls.SCREEN_RESPONSES["SELECT_COUNTRY"])
        
        # Formatear países
        formatted_countries = []
        for country in countries:
            if country:  # Asegurarse de que no sea None o vacío
                formatted_countries.append({
                    "id": f"country_{country}",
                    "title": country
                })
        
        # Actualizar datos en la respuesta
        screen_response["data"]["available_countries"] = formatted_countries
        
        # Convertir todos los objetos de traducción a strings para que sean serializables
        return ensure_serializable(screen_response)
    
    @classmethod
    def _get_fixtures_screen(cls, country):
        """
        Genera la pantalla de selección de partidos para un país específico.
        
        Args:
            country: Nombre del país seleccionado
            
        Returns:
            dict: Estructura de la pantalla para WhatsApp Flows.
        """
        logger.debug(f"Generando pantalla SELECT_FIXTURE para país {country}")
        
        # Obtener partidos del país seleccionado, limitado a los más recientes
        fixtures = FixtureData.objects.filter(
            league_country=country
        ).order_by('-date')[:20]  # Limitamos a 20 partidos para evitar sobrecarga
        
        # Crear una copia de la respuesta base
        screen_response = dict(cls.SCREEN_RESPONSES["SELECT_FIXTURE"])
        
        # Actualizar nombre del país
        screen_response["data"]["country_name"] = country
        
        # Formatear partidos
        formatted_fixtures = []
        for fixture in fixtures:
            if fixture.fixture_id:  # Asegurarse de que no sea None
                # Acortar nombres de equipos si son demasiado largos
                home_team = cls._truncate_team_name(fixture.home_team_name)
                away_team = cls._truncate_team_name(fixture.away_team_name)
                
                # Formatear el marcador, mostrando 0 en lugar de - cuando corresponda
                home_goals = "0" if fixture.home_goals == 0 else (fixture.home_goals or "-")
                away_goals = "0" if fixture.away_goals == 0 else (fixture.away_goals or "-")
                
                # Crear título abreviado que no exceda 30 caracteres
                score_text = f"{home_team} {home_goals}:{away_goals} {away_team}"
                
                # Truncar si aún es demasiado largo
                if len(score_text) > 30:
                    score_text = score_text[:27] + "..."
                
                status = fixture.status_long
                date_str = fixture.date.strftime("%d/%m/%Y %H:%M") if fixture.date else "Sin fecha"
                
                formatted_fixtures.append({
                    "id": f"fixture_{fixture.fixture_id}",
                    "title": score_text,
                    "description": f"{date_str} | {status}"
                })
        
        # Actualizar datos en la respuesta
        screen_response["data"]["available_fixtures"] = formatted_fixtures
        
        # Convertir todos los objetos de traducción a strings para que sean serializables
        return ensure_serializable(screen_response)
    
    @classmethod
    def _truncate_team_name(cls, team_name):
        """
        Acorta el nombre del equipo para que sea más adecuado para mostrar en WhatsApp.
        
        Args:
            team_name: Nombre completo del equipo
            
        Returns:
            str: Nombre del equipo acortado
        """
        # Lista de palabras comunes a eliminar
        common_words = ['FC', 'CF', 'Club', 'Sporting', 'Athletic', 'United', 'Deportivo', 'CD', 'Real', 'Atlético']
        
        # Intentar primero eliminar palabras comunes
        shortened_name = team_name
        for word in common_words:
            if word in shortened_name:
                shortened_name = shortened_name.replace(f" {word}", "").replace(f"{word} ", "")
                
        # Si aún es muy largo, truncar
        if len(shortened_name) > 10:
            shortened_name = shortened_name[:10]
            
        return shortened_name
    
    @classmethod
    def _get_fixture_detail_screen(cls, fixture_id):
        """
        Genera la pantalla con detalles de un partido específico.
        
        Args:
            fixture_id: ID del partido seleccionado
            
        Returns:
            dict: Estructura de la pantalla para WhatsApp Flows.
        """
        logger.debug(f"Generando pantalla FIXTURE_DETAIL para partido ID: {fixture_id}")
        
        # Obtener datos del partido
        try:
            logger.info(f"Buscando datos del partido con ID {fixture_id}")
            fixture = FixtureData.objects.get(fixture_id=fixture_id)
            
            # Crear una copia de la respuesta base
            screen_response = dict(cls.SCREEN_RESPONSES["FIXTURE_DETAIL"])
            
            # Actualizar ID del partido
            screen_response["data"]["fixture_id"] = fixture_id
            
            # Preparar información sobre el ganador
            if fixture.home_team_winner is True:
                winner_text = f"**Ganando:** *{fixture.home_team_name}*"
            elif fixture.away_team_winner is True:
                winner_text = f"**Ganando:** *{fixture.away_team_name}*"
            elif fixture.status_short in ["FT", "AET", "PEN"]:
                winner_text = "**Resultado:** *Empate*"
            else:
                winner_text = "**Estado:** *En juego o no finalizado*"
            
            # Preparar texto para el marcador
            score = f"{0 if fixture.home_goals == 0 else (fixture.home_goals or '-')} - {0 if fixture.away_goals == 0 else (fixture.away_goals or '-')}"
            
            # Crear contenido en formato markdown para RichText
            markdown_content = [
                f"# {fixture.home_team_name} vs {fixture.away_team_name}",
                f"## 🏆 {fixture.league_name} ({fixture.league_country})",
                "",
                f"### Información del Partido",
                f"**ID del partido:** {fixture_id}",
                f"**Marcador:** *{score}*",
                f"**Estado:** *{fixture.status_long}*",
                f"**Minuto:** *{fixture.elapsed} min*" if fixture.elapsed else "**Minuto:** *N/A*",
                winner_text,
                f"**Fecha y Hora:** *{fixture.date.strftime('%d/%m/%Y %H:%M')}*" if fixture.date else "**Fecha y Hora:** *Sin fecha*",
                "",
                "### Equipos",
                f"+ **Local:** *{fixture.home_team_name}*",
                f"+ **Visitante:** *{fixture.away_team_name}*",
                ""
            ]
            
            # Añadir información adicional si está disponible
            if fixture.venue_name:
                markdown_content.append(f"**Estadio:** *{fixture.venue_name}*")
                if fixture.venue_city:
                    markdown_content.append(f"**Ciudad:** *{fixture.venue_city}*")
                markdown_content.append("")
            
            # Añadir información de half time si está disponible
            if fixture.home_halftime is not None and fixture.away_halftime is not None:
                markdown_content.append("### Detalles por Tiempos")
                markdown_content.append(f"**Primer Tiempo:** *{fixture.home_halftime} - {fixture.away_halftime}*")
                
                if fixture.home_fulltime is not None and fixture.away_fulltime is not None:
                    markdown_content.append(f"**Tiempo Completo:** *{fixture.home_fulltime} - {fixture.away_fulltime}*")
                
                if fixture.home_extratime is not None and fixture.away_extratime is not None:
                    markdown_content.append(f"**Tiempo Extra:** *{fixture.home_extratime} - {fixture.away_extratime}*")
                
                if fixture.home_penalty is not None and fixture.away_penalty is not None:
                    markdown_content.append(f"**Penaltis:** *{fixture.home_penalty} - {fixture.away_penalty}*")
            
            # Actualizar datos en la respuesta
            screen_response["data"]["fixture_details"] = {
                "markdown_content": markdown_content
            }
            
            # Convertir todos los objetos de traducción a strings para que sean serializables
            return ensure_serializable(screen_response)
        except FixtureData.DoesNotExist:
            logger.error(f"No se encontró el partido con ID {fixture_id}")
            return cls._get_countries_screen()
    
    @classmethod
    def _get_next_step_screen(cls, fixture_id):
        """
        Genera la pantalla con opciones para las próximas acciones después de ver los detalles del partido.
        
        Args:
            fixture_id: ID del partido consultado
            
        Returns:
            dict: Estructura de la pantalla para WhatsApp Flows.
        """
        logger.debug(f"Generando pantalla NEXT_STEP para partido ID: {fixture_id}")
        
        # Crear una copia de la respuesta base
        screen_response = dict(cls.SCREEN_RESPONSES["NEXT_STEP"])
        
        # Actualizar ID del partido
        screen_response["data"]["fixture_id"] = fixture_id
        
        # Preparar las próximas acciones disponibles
        next_actions = [
            {"id": "action_finish", "title": "Finalizar consulta"},
            {"id": "action_predictions", "title": "Asistente para predicciones"},
            {"id": "action_live_odds", "title": "Asistente para Probabilidades"},
            {"id": "action_betting", "title": "Asistente para apuestas"}
        ]
        
        screen_response["data"]["next_actions"] = next_actions
        
        # Convertir todos los objetos de traducción a strings para que sean serializables
        return ensure_serializable(screen_response)
    
    @classmethod
    def generate_flow_json(cls):
        """
        Genera el JSON completo para WhatsApp Flows según la documentación oficial de Meta.
        
        Returns:
            dict: Estructura completa del flujo para WhatsApp según el formato de Meta.
        """
        flow_json = {
            "version": "7.0",
            "data_api_version": "3.0",
            "routing_model": {
                "WELCOME": ["SELECT_COUNTRY"],
                "SELECT_COUNTRY": ["SELECT_FIXTURE"],
                "SELECT_FIXTURE": ["FIXTURE_DETAIL"],
                "FIXTURE_DETAIL": ["NEXT_STEP"],
                "NEXT_STEP": []  # Terminal screen
            },
            "screens": [
                # Pantalla inicial: Bienvenida y selección de opciones
                {
                    "id": "WELCOME",
                    "title": "Pantalla de bienvenida",
                    "layout": {
                        "type": "SingleColumnLayout",
                        "children": [
                            {
                                "type": "Form",
                                "name": "flow_path",
                                "children": [
                                    {
                                        "type": "Image",
                                        "src": "iVBORw0KGC",
                                        "height": 60,
                                        "scale-type": "cover"
                                    },
                                    {
                                        "type": "TextBody",
                                        "markdown": True,
                                        "text": [
                                            "**Consulta partidos en vivo**, mediante el **asistente inteligente** que te ayuda con *estadísticas personalizadas* y obtener **recomendaciones para tus apuestas.**",                    
                                            "Funciones destacadas:",
                                            "- 📺 Partidos en tiempo real",
                                            "- 📊 Análisis estadístico personalizado",                 
                                            "Consultar terminos y condiciones [aquí](https://www.deep90.com/) en Deep90.com"
                                        ]
                                    },
                                    {
                                        "type": "CheckboxGroup",
                                        "name": "Selecciona_opcion_b9cdae",
                                        "label": "Selecciona opcion",
                                        "required": True,
                                        "data-source": [
                                            {
                                                "id": "0_Resultados_en_vivo",
                                                "title": "Acepto Terminos y condiciones"
                                            }
                                        ]
                                    },                            
                                    {
                                        "type": "Footer",
                                        "label": "Continue",
                                        "on-click-action": {
                                            "name": "data_exchange",
                                            "payload": {
                                                "selected_option": "${form.Selecciona_opcion_b9cdae}"
                                            }
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                },
                # Pantalla 1: Selección de país
                {
                    "id": "SELECT_COUNTRY",
                    "title": "Selección de País",
                    "data": {
                        "available_countries": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "title": {"type": "string"}
                                }
                            },
                            "__example__": [
                                {"id": "country_España", "title": "España"},
                                {"id": "country_Inglaterra", "title": "Inglaterra"},
                                {"id": "country_Italia", "title": "Italia"}
                            ]
                        }
                    },
                    "layout": {
                        "type": "SingleColumnLayout",
                        "children": [
                            {
                                "type": "Form",
                                "name": "country_form",
                                "children": [
                                    {
                                        "type": "TextSubheading",
                                        "text": "Selecciona un país para ver sus partidos"
                                    },
                                    {
                                        "type": "RadioButtonsGroup",
                                        "label": "Países disponibles",
                                        "name": "selected_country",
                                        "data-source": "${data.available_countries}",
                                        "required": True
                                    },
                                    {
                                        "type": "Footer",
                                        "label": "Ver partidos",
                                        "on-click-action": {
                                            "name": "data_exchange",
                                            "payload": {
                                                "selected_country": "${form.selected_country}"
                                            }
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                },
                # Pantalla 2: Selección de partido
                {
                    "id": "SELECT_FIXTURE",
                    "title": "Partidos Disponibles",
                    "data": {
                        "country_name": {
                            "type": "string",
                            "__example__": "España"
                        },
                        "available_fixtures": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "title": {"type": "string"},
                                    "description": {"type": "string"}
                                }
                            },
                            "__example__": [
                                {
                                    "id": "fixture_1234",
                                    "title": "Barcelona 2 - 1 Junior",
                                    "description": "12/04/2025 20:00 | Finalizado"
                                },
                                {
                                    "id": "fixture_1235",
                                    "title": "Atlético Madrid 3 - 0 Sevilla",
                                    "description": "12/04/2025 18:30 | Finalizado"
                                }
                            ]
                        }
                    },
                    "layout": {
                        "type": "SingleColumnLayout",
                        "children": [
                            {
                                "type": "Form",
                                "name": "fixture_form",
                                "children": [
                                    {
                                        "type": "TextSubheading",
                                        "text": "Partidos de disponibles"
                                    },
                                    {
                                        "type": "RadioButtonsGroup",
                                        "label": "Selecciona un partido",
                                        "name": "selected_fixture",
                                        "data-source": "${data.available_fixtures}",
                                        "required": True
                                    },
                                    {
                                        "type": "Footer",
                                        "label": "Ver detalles",
                                        "on-click-action": {
                                            "name": "data_exchange",
                                            "payload": {
                                                "selected_fixture": "${form.selected_fixture}",
                                                "country_name": "${data.country_name}"
                                            }
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                },
                # Pantalla 3: Detalles del partido
                {
                    "id": "FIXTURE_DETAIL",
                    "title": "Detalles del Partido",
                    "data": {
                        "fixture_id": {
                            "type": "number",
                            "__example__": 1234
                        },
                        "fixture_details": {
                            "type": "object",
                            "properties": {
                                "markdown_content": {
                                    "type": "array",
                                    "items": {
                                        "type": "string"
                                    }
                                }
                            },
                            "__example__": {
                                "markdown_content": [
                                    "# Barcelona vs Real Madrid",
                                    "## 🏆 LaLiga (España)",
                                    "",
                                    "### Información del Partido",
                                    "**ID del partido:** 1234",
                                    "**Marcador:** *2 - 1*",
                                    "**Estado:** *En juego*",
                                    "**Minuto:** *45 min*",
                                    "**Ganando:** *Barcelona*",
                                    "**Fecha y Hora:** *12/04/2025 20:00*"
                                ]
                            }
                        }
                    },
                    "layout": {
                        "type": "SingleColumnLayout",
                        "children": [
                            {
                                "type": "RichText",
                                "text": "${data.fixture_details.markdown_content}"
                            },
                            {
                                "type": "Footer",
                                "label": "Continuar",
                                "on-click-action": {
                                    "name": "data_exchange",
                                    "payload": {
                                        "fixture_id": "${data.fixture_id}"
                                    }
                                }
                            }
                        ]
                    }
                },
                # Pantalla 4: Próximos pasos
                {
                    "id": "NEXT_STEP",
                    "title": "¿Qué deseas hacer ahora?",
                    "terminal": True,
                    "data": {
                        "fixture_id": {
                            "type": "number",
                            "__example__": 1234
                        },
                        "next_actions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "title": {"type": "string"}
                                }
                            },
                            "__example__": [
                                {"id": "action_finish", "title": "Finalizar consulta"},
                                {"id": "action_predictions", "title": "Asistente para predicciones"},
                                {"id": "action_live_odds", "title": "Asistente para Probabilidades"},
                                {"id": "action_betting", "title": "Asistente para apuestas"}
                            ]
                        }
                    },
                    "layout": {
                        "type": "SingleColumnLayout",
                        "children": [
                            {
                                "type": "Form",
                                "name": "next_step_form",
                                "children": [
                                    {
                                        "type": "TextSubheading",
                                        "text": "Selecciona tu próxima acción"
                                    },
                                    {
                                        "type": "RadioButtonsGroup",
                                        "label": "Acciones disponibles",
                                        "name": "selected_action",
                                        "data-source": "${data.next_actions}",
                                        "required": True
                                    },
                                    {
                                        "type": "Footer",
                                        "label": "Continuar",
                                        "on-click-action": {
                                            "name": "complete",
                                            "payload": {
                                                "selected_action": "${form.selected_action}",
                                                "fixture_id": "${data.fixture_id}",
                                                "id_flujo": "1033636801988224"
                                            }
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                }
            ]
        }
        
        return ensure_serializable(flow_json)