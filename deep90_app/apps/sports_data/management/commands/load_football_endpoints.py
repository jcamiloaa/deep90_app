import os
from django.core.management.base import BaseCommand
from deep90_app.apps.sports_data.models import APIEndpoint, APIParameter


class Command(BaseCommand):
    help = 'Carga endpoints iniciales para la API de fútbol'

    def handle(self, *args, **kwargs):
        self.stdout.write('Cargando endpoints iniciales para la API de fútbol...')
        
        # Endpoint de Timezone (sin parámetros)
        timezone_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Zonas Horarias',
            endpoint='timezone',
            description='Obtiene la lista de zonas horarias disponibles para usar en el endpoint de partidos. No requiere parámetros. Contiene todas las zonas horarias existentes.',
            has_parameters=False
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{timezone_endpoint.name}" creado correctamente'))
        else:
            self.stdout.write(f'Endpoint "{timezone_endpoint.name}" ya existe')
        
        # Endpoint de países (sin parámetros)
        countries_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Países',
            endpoint='countries',
            description='Obtiene la lista de todos los países disponibles',
            has_parameters=False
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{countries_endpoint.name}" creado correctamente'))
        else:
            self.stdout.write(f'Endpoint "{countries_endpoint.name}" ya existe')
        
        # Endpoint de ligas (con parámetros)
        leagues_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Ligas',
            endpoint='leagues',
            description='Obtiene la lista de ligas y copas disponibles',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{leagues_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para ligas
            parameters = [
                {
                    'name': 'id',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID de la liga'
                },
                {
                    'name': 'name',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'El nombre de la liga'
                },
                {
                    'name': 'country',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'El país de la liga'
                },
                {
                    'name': 'code',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'El código Alpha del país (FR, GB-ENG, IT...)'
                },
                {
                    'name': 'season',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'La temporada de la liga (formato YYYY)'
                },
                {
                    'name': 'team',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del equipo'
                },
                {
                    'name': 'type',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'El tipo de la liga (league o cup)'
                },
                {
                    'name': 'current',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'Estado de la liga (true o false)'
                },
                {
                    'name': 'search',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'Búsqueda por nombre o país de la liga (mínimo 3 caracteres)'
                },
                {
                    'name': 'last',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'Las últimas X ligas/copas añadidas en la API'
                },
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=leagues_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{leagues_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{leagues_endpoint.name}" ya existe')
            
        # Endpoint de temporadas (sin parámetros)
        seasons_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Temporadas',
            endpoint='leagues/seasons',
            description='Obtiene la lista de temporadas disponibles',
            has_parameters=False
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{seasons_endpoint.name}" creado correctamente'))
        else:
            self.stdout.write(f'Endpoint "{seasons_endpoint.name}" ya existe')
            
        # Endpoint de equipos (con parámetros)
        teams_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Equipos',
            endpoint='teams',
            description='Obtiene información sobre equipos según varios criterios',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{teams_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para equipos
            parameters = [
                {
                    'name': 'id',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del equipo'
                },
                {
                    'name': 'name',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'El nombre del equipo'
                },
                {
                    'name': 'league',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID de la liga'
                },
                {
                    'name': 'season',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'La temporada de la liga (formato YYYY)'
                },
                {
                    'name': 'country',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'El nombre del país del equipo'
                },
                {
                    'name': 'code',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'El código del equipo (3 caracteres)'
                },
                {
                    'name': 'venue',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del estadio'
                },
                {
                    'name': 'search',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'Búsqueda por nombre o país del equipo (mínimo 3 caracteres)'
                },
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=teams_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{teams_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{teams_endpoint.name}" ya existe')
        
        # Endpoint de estadísticas de equipos
        teams_stats_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Estadísticas de Equipos',
            endpoint='teams/statistics',
            description='Devuelve estadísticas de un equipo en relación con una competición y temporada dada',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{teams_stats_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para estadísticas de equipos
            parameters = [
                {
                    'name': 'league',
                    'parameter_type': 'integer',
                    'required': True,
                    'description': 'El ID de la liga'
                },
                {
                    'name': 'season',
                    'parameter_type': 'integer',
                    'required': True,
                    'description': 'La temporada de la liga (formato YYYY)'
                },
                {
                    'name': 'team',
                    'parameter_type': 'integer',
                    'required': True,
                    'description': 'El ID del equipo'
                },
                {
                    'name': 'date',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'La fecha límite (formato YYYY-MM-DD)'
                },
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=teams_stats_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{teams_stats_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{teams_stats_endpoint.name}" ya existe')

        # Endpoint de temporadas de equipos
        teams_seasons_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Temporadas de Equipos',
            endpoint='teams/seasons',
            description='Obtiene la lista de temporadas disponibles para un equipo',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{teams_seasons_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para temporadas de equipos
            parameters = [
                {
                    'name': 'team',
                    'parameter_type': 'integer',
                    'required': True,
                    'description': 'El ID del equipo'
                }
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=teams_seasons_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{teams_seasons_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{teams_seasons_endpoint.name}" ya existe')

        # Endpoint de países de equipos
        teams_countries_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Países de Equipos',
            endpoint='teams/countries',
            description='Obtiene la lista de países disponibles para el endpoint de equipos',
            has_parameters=False
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{teams_countries_endpoint.name}" creado correctamente'))
        else:
            self.stdout.write(f'Endpoint "{teams_countries_endpoint.name}" ya existe')
            
        # Endpoint de estadios (con parámetros)
        venues_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Estadios',
            endpoint='venues',
            description='Obtiene la lista de estadios disponibles según varios criterios',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{venues_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para estadios
            parameters = [
                {
                    'name': 'id',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del estadio'
                },
                {
                    'name': 'name',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'El nombre del estadio'
                },
                {
                    'name': 'city',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'La ciudad del estadio'
                },
                {
                    'name': 'country',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'El país del estadio'
                },
                {
                    'name': 'search',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'Búsqueda por nombre, ciudad o país del estadio (mínimo 3 caracteres)'
                },
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=venues_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{venues_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{venues_endpoint.name}" ya existe')
        
        # Endpoint de clasificaciones (con parámetros)
        standings_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Clasificaciones',
            endpoint='standings',
            description='Obtiene la clasificación de una liga o equipo. Devuelve una tabla con uno o más rankings según la liga o copa',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{standings_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para clasificaciones
            parameters = [
                {
                    'name': 'league',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID de la liga'
                },
                {
                    'name': 'season',
                    'parameter_type': 'integer',
                    'required': True,
                    'description': 'La temporada de la liga (formato YYYY)'
                },
                {
                    'name': 'team',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del equipo'
                },
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=standings_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{standings_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{standings_endpoint.name}" ya existe')
        
        # 1. Endpoint Rounds
        rounds_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Rondas',
            endpoint='fixtures/rounds',
            description='Obtiene las rondas de una liga o copa. Las rondas se pueden usar como filtros en el endpoint de partidos',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{rounds_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para rondas
            parameters = [
                {
                    'name': 'league',
                    'parameter_type': 'integer',
                    'required': True,
                    'description': 'El ID de la liga'
                },
                {
                    'name': 'season',
                    'parameter_type': 'integer',
                    'required': True,
                    'description': 'La temporada de la liga (formato YYYY)'
                },
                {
                    'name': 'current',
                    'parameter_type': 'boolean',
                    'required': False,
                    'description': 'Solo la ronda actual (true/false)'
                },
                {
                    'name': 'dates',
                    'parameter_type': 'boolean',
                    'required': False,
                    'description': 'Añadir las fechas de cada ronda en la respuesta (true/false)'
                },
                {
                    'name': 'timezone',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'Una zona horaria válida del endpoint Timezone'
                }
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=rounds_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{rounds_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{rounds_endpoint.name}" ya existe')
        
        # 2. Endpoint Fixtures
        fixtures_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Partidos',
            endpoint='fixtures',
            description='Obtiene información sobre partidos según varios criterios. Se puede usar el parámetro timezone para obtener los horarios en la zona horaria deseada',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{fixtures_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para partidos
            parameters = [
                {
                    'name': 'id',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del partido'
                },
                {
                    'name': 'ids',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'Uno o más IDs de partidos (máximo 20, formato: "id-id-id")'
                },
                {
                    'name': 'live',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'Todos los partidos en vivo o varios IDs de ligas (all o id-id)'
                },
                {
                    'name': 'date',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'Una fecha válida (formato YYYY-MM-DD)'
                },
                {
                    'name': 'league',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID de la liga'
                },
                {
                    'name': 'season',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'La temporada de la liga (formato YYYY)'
                },
                {
                    'name': 'team',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del equipo'
                },
                {
                    'name': 'last',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'Los últimos X partidos (máximo 2 caracteres)'
                },
                {
                    'name': 'next',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'Los próximos X partidos (máximo 2 caracteres)'
                },
                {
                    'name': 'from',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'Una fecha válida desde (formato YYYY-MM-DD)'
                },
                {
                    'name': 'to',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'Una fecha válida hasta (formato YYYY-MM-DD)'
                },
                {
                    'name': 'round',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'La ronda del partido'
                },
                {
                    'name': 'status',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'Uno o más estados de partido (Ej: NS, NS-PST-FT)'
                },
                {
                    'name': 'venue',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del estadio del partido'
                },
                {
                    'name': 'timezone',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'Una zona horaria válida del endpoint Timezone'
                }
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=fixtures_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{fixtures_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{fixtures_endpoint.name}" ya existe')
            
        # 3. Endpoint Head To Head
        h2h_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Enfrentamientos Directos',
            endpoint='fixtures/headtohead',
            description='Obtiene los enfrentamientos directos entre dos equipos',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{h2h_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para enfrentamientos directos
            parameters = [
                {
                    'name': 'h2h',
                    'parameter_type': 'string',
                    'required': True,
                    'description': 'Los IDs de los equipos (formato: ID-ID)'
                },
                {
                    'name': 'date',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'Una fecha válida (formato YYYY-MM-DD)'
                },
                {
                    'name': 'league',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID de la liga'
                },
                {
                    'name': 'season',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'La temporada de la liga (formato YYYY)'
                },
                {
                    'name': 'last',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'Los últimos X partidos'
                },
                {
                    'name': 'next',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'Los próximos X partidos'
                },
                {
                    'name': 'from',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'Una fecha válida desde (formato YYYY-MM-DD)'
                },
                {
                    'name': 'to',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'Una fecha válida hasta (formato YYYY-MM-DD)'
                },
                {
                    'name': 'status',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'Uno o más estados de partido (Ej: NS, NS-PST-FT)'
                },
                {
                    'name': 'venue',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del estadio'
                },
                {
                    'name': 'timezone',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'Una zona horaria válida del endpoint Timezone'
                }
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=h2h_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{h2h_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{h2h_endpoint.name}" ya existe')
            
        # 4. Endpoint Statistics
        statistics_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Estadísticas de Partido',
            endpoint='fixtures/statistics',
            description='Obtiene las estadísticas de un partido incluyendo disparos a puerta, posesión, tarjetas, etc',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{statistics_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para estadísticas
            parameters = [
                {
                    'name': 'fixture',
                    'parameter_type': 'integer',
                    'required': True,
                    'description': 'El ID del partido'
                },
                {
                    'name': 'team',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del equipo'
                },
                {
                    'name': 'type',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'El tipo de estadística'
                },
                {
                    'name': 'half',
                    'parameter_type': 'boolean',
                    'required': False,
                    'description': 'Añadir estadísticas del primer tiempo (true/false). Datos disponibles desde temporada 2024'
                }
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=statistics_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{statistics_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{statistics_endpoint.name}" ya existe')
            
        # 5. Endpoint Events
        events_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Eventos',
            endpoint='fixtures/events',
            description='Obtiene los eventos de un partido (goles, tarjetas, sustituciones, VAR)',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{events_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para eventos
            parameters = [
                {
                    'name': 'fixture',
                    'parameter_type': 'integer',
                    'required': True,
                    'description': 'El ID del partido'
                },
                {
                    'name': 'team',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del equipo'
                },
                {
                    'name': 'player',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del jugador'
                },
                {
                    'name': 'type',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'El tipo de evento'
                }
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=events_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{events_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{events_endpoint.name}" ya existe')
            
        # 6. Endpoint Lineups
        lineups_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Alineaciones',
            endpoint='fixtures/lineups',
            description='Obtiene las alineaciones de un partido (formación, entrenador, once inicial, suplentes, posición de jugadores)',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{lineups_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para alineaciones
            parameters = [
                {
                    'name': 'fixture',
                    'parameter_type': 'integer',
                    'required': True,
                    'description': 'El ID del partido'
                },
                {
                    'name': 'team',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del equipo'
                },
                {
                    'name': 'player',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del jugador'
                },
                {
                    'name': 'type',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'El tipo'
                }
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=lineups_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{lineups_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{lineups_endpoint.name}" ya existe')
            
        # 7. Endpoint Players Statistics
        players_statistics_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Estadísticas de Jugadores',
            endpoint='fixtures/players',
            description='Obtiene las estadísticas de los jugadores de un partido',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{players_statistics_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para estadísticas de jugadores
            parameters = [
                {
                    'name': 'fixture',
                    'parameter_type': 'integer',
                    'required': True,
                    'description': 'El ID del partido'
                },
                {
                    'name': 'team',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del equipo'
                }
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=players_statistics_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{players_statistics_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{players_statistics_endpoint.name}" ya existe')

        # Endpoint de lesiones (con parámetros)
        injuries_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Lesiones',
            endpoint='injuries',
            description='Obtiene la lista de jugadores que no participan en partidos por diversas razones como suspensión o lesión',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{injuries_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para lesiones
            parameters = [
                {
                    'name': 'league',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID de la liga'
                },
                {
                    'name': 'season',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'La temporada de la liga (formato YYYY). Requerido con league, team y player'
                },
                {
                    'name': 'fixture',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del partido'
                },
                {
                    'name': 'team',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del equipo'
                },
                {
                    'name': 'player',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del jugador'
                },
                {
                    'name': 'date',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'Una fecha válida (formato YYYY-MM-DD)'
                },
                {
                    'name': 'ids',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'Uno o más IDs de partidos (máximo 20, formato: "id-id-id")'
                },
                {
                    'name': 'timezone',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'Una zona horaria válida del endpoint Timezone'
                }
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=injuries_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{injuries_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{injuries_endpoint.name}" ya existe')
        
        # Endpoint de predicciones (con parámetros)
        predictions_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Predicciones',
            endpoint='predictions',
            description='Obtiene predicciones sobre un partido utilizando algoritmos como distribución de Poisson, comparación de estadísticas de equipos, últimos partidos y jugadores',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{predictions_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para predicciones
            parameters = [
                {
                    'name': 'fixture',
                    'parameter_type': 'integer',
                    'required': True,
                    'description': 'El ID del partido'
                }
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=predictions_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{predictions_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{predictions_endpoint.name}" ya existe')
        
        # Endpoint de entrenadores (con parámetros)
        coachs_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Entrenadores',
            endpoint='coachs',
            description='Obtiene toda la información sobre los entrenadores y sus carreras. Para obtener la foto de un entrenador, utilizar: https://media.api-sports.io/football/coachs/{coach_id}.png',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{coachs_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para entrenadores
            parameters = [
                {
                    'name': 'id',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del entrenador'
                },
                {
                    'name': 'team',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del equipo'
                },
                {
                    'name': 'search',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'El nombre del entrenador (mínimo 3 caracteres)'
                }
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=coachs_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{coachs_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{coachs_endpoint.name}" ya existe')
        
        # 1. Endpoint Players Seasons
        players_seasons_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Temporadas de Jugadores',
            endpoint='players/seasons',
            description='Obtiene todas las temporadas disponibles para estadísticas de jugadores',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{players_seasons_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para temporadas de jugadores
            parameters = [
                {
                    'name': 'player',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del jugador'
                }
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=players_seasons_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{players_seasons_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{players_seasons_endpoint.name}" ya existe')
        
        # 2. Endpoint Players Profiles
        players_profiles_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Perfiles de Jugadores',
            endpoint='players',
            description='Obtiene la lista de todos los jugadores disponibles. Usa paginación (250 resultados por página). Para obtener la foto del jugador: https://media.api-sports.io/football/players/{player_id}.png',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{players_profiles_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para perfiles de jugadores
            parameters = [
                {
                    'name': 'player',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del jugador'
                },
                {
                    'name': 'search',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'El apellido del jugador (mínimo 3 caracteres)'
                },
                {
                    'name': 'page',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'Número de página para paginación (predeterminado: 1)'
                }
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=players_profiles_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{players_profiles_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{players_profiles_endpoint.name}" ya existe')
        
        # 3. Endpoint Players Statistics
        players_statistics_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Estadísticas de Jugadores',
            endpoint='players',
            description='Obtiene estadísticas de jugadores. Devuelve jugadores con datos de perfil y estadísticas disponibles. Usa paginación (20 resultados por página)',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{players_statistics_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para estadísticas de jugadores
            parameters = [
                {
                    'name': 'id',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del jugador'
                },
                {
                    'name': 'team',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del equipo'
                },
                {
                    'name': 'league',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID de la liga'
                },
                {
                    'name': 'season',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'La temporada de la liga (formato YYYY). Requiere los campos Id, League o Team'
                },
                {
                    'name': 'search',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'El nombre del jugador (mínimo 4 caracteres). Requiere los campos League o Team'
                },
                {
                    'name': 'page',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'Número de página para paginación (predeterminado: 1)'
                }
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=players_statistics_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{players_statistics_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{players_statistics_endpoint.name}" ya existe')
        
        # 4. Endpoint Players Squads
        players_squads_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Plantillas de Equipos',
            endpoint='players/squads',
            description='Devuelve la plantilla actual de un equipo o los equipos asociados a un jugador. Requiere al menos un parámetro',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{players_squads_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para plantillas de equipos
            parameters = [
                {
                    'name': 'team',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del equipo'
                },
                {
                    'name': 'player',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del jugador'
                }
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=players_squads_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{players_squads_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{players_squads_endpoint.name}" ya existe')
        
        # 5. Endpoint Players Teams
        players_teams_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Equipos de Jugadores',
            endpoint='players/teams',
            description='Devuelve la lista de equipos y temporadas en las que jugó el jugador durante su carrera',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{players_teams_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para equipos de jugadores
            parameters = [
                {
                    'name': 'player',
                    'parameter_type': 'integer',
                    'required': True,
                    'description': 'El ID del jugador'
                }
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=players_teams_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{players_teams_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{players_teams_endpoint.name}" ya existe')
        
        # 6. Endpoint Top Scorers
        top_scorers_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Máximos Goleadores',
            endpoint='players/topscorers',
            description='Obtiene los 20 mejores jugadores goleadores para una liga o copa. Ordenados por número de goles, penaltis, asistencias, partidos, minutos jugados, etc.',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{top_scorers_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para máximos goleadores
            parameters = [
                {
                    'name': 'league',
                    'parameter_type': 'integer',
                    'required': True,
                    'description': 'El ID de la liga'
                },
                {
                    'name': 'season',
                    'parameter_type': 'integer',
                    'required': True,
                    'description': 'La temporada de la liga (formato YYYY)'
                }
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=top_scorers_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{top_scorers_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{top_scorers_endpoint.name}" ya existe')
        
        # 7. Endpoint Top Assists
        top_assists_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Máximos Asistentes',
            endpoint='players/topassists',
            description='Obtiene los 20 mejores asistentes para una liga o copa. Ordenados por número de asistencias, goles, penaltis, partidos, etc.',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{top_assists_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para máximos asistentes
            parameters = [
                {
                    'name': 'league',
                    'parameter_type': 'integer',
                    'required': True,
                    'description': 'El ID de la liga'
                },
                {
                    'name': 'season',
                    'parameter_type': 'integer',
                    'required': True,
                    'description': 'La temporada de la liga (formato YYYY)'
                }
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=top_assists_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{top_assists_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{top_assists_endpoint.name}" ya existe')
        
        # 8. Endpoint Top Yellow Cards
        top_yellow_cards_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Más Tarjetas Amarillas',
            endpoint='players/topyellowcards',
            description='Obtiene los 20 jugadores con más tarjetas amarillas para una liga o copa. Ordenados por número de tarjetas amarillas, rojas, partidos, etc.',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{top_yellow_cards_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para más tarjetas amarillas
            parameters = [
                {
                    'name': 'league',
                    'parameter_type': 'integer',
                    'required': True,
                    'description': 'El ID de la liga'
                },
                {
                    'name': 'season',
                    'parameter_type': 'integer',
                    'required': True,
                    'description': 'La temporada de la liga (formato YYYY)'
                }
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=top_yellow_cards_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{top_yellow_cards_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{top_yellow_cards_endpoint.name}" ya existe')
        
        # 9. Endpoint Top Red Cards
        top_red_cards_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Más Tarjetas Rojas',
            endpoint='players/topredcards',
            description='Obtiene los 20 jugadores con más tarjetas rojas para una liga o copa. Ordenados por número de tarjetas rojas, amarillas, partidos, etc.',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{top_red_cards_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para más tarjetas rojas
            parameters = [
                {
                    'name': 'league',
                    'parameter_type': 'integer',
                    'required': True,
                    'description': 'El ID de la liga'
                },
                {
                    'name': 'season',
                    'parameter_type': 'integer',
                    'required': True,
                    'description': 'La temporada de la liga (formato YYYY)'
                }
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=top_red_cards_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{top_red_cards_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{top_red_cards_endpoint.name}" ya existe')
        
        # Endpoint de transferencias (con parámetros)
        transfers_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Transferencias',
            endpoint='transfers',
            description='Obtiene todas las transferencias disponibles para jugadores y equipos',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{transfers_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para transferencias
            parameters = [
                {
                    'name': 'player',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del jugador'
                },
                {
                    'name': 'team',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del equipo'
                }
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=transfers_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{transfers_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{transfers_endpoint.name}" ya existe')
        
        # Endpoint de trofeos (con parámetros)
        trophies_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Trofeos',
            endpoint='trophies',
            description='Obtiene todos los trofeos disponibles para un jugador o entrenador',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{trophies_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para trofeos
            parameters = [
                {
                    'name': 'player',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del jugador'
                },
                {
                    'name': 'players',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'Uno o más IDs de jugadores (máximo 20, formato: "id-id-id")'
                },
                {
                    'name': 'coach',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del entrenador'
                },
                {
                    'name': 'coachs',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'Uno o más IDs de entrenadores (máximo 20, formato: "id-id-id")'
                }
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=trophies_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{trophies_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{trophies_endpoint.name}" ya existe')
        
        # Endpoint de suspendidos/lesionados (con parámetros)
        sidelined_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Suspendidos/Lesionados',
            endpoint='sidelined',
            description='Obtiene información sobre jugadores o entrenadores que están temporalmente fuera de acción por lesión, suspensión u otras razones',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{sidelined_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para suspendidos/lesionados
            parameters = [
                {
                    'name': 'player',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del jugador'
                },
                {
                    'name': 'players',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'Uno o más IDs de jugadores (máximo 20, formato: "id-id-id")'
                },
                {
                    'name': 'coach',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del entrenador'
                },
                {
                    'name': 'coachs',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'Uno o más IDs de entrenadores (máximo 20, formato: "id-id-id")'
                }
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=sidelined_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{sidelined_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{sidelined_endpoint.name}" ya existe')
        
        # Endpoint de cuotas en vivo (con parámetros)
        odds_live_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Cuotas en Vivo',
            endpoint='odds/live',
            description='Obtiene cuotas en tiempo real para partidos en curso. Los partidos se agregan entre 15 y 5 minutos antes del inicio y se eliminan entre 5 y 20 minutos después de finalizar. Actualización cada 5-60 segundos.',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{odds_live_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para cuotas en vivo
            parameters = [
                {
                    'name': 'fixture',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del partido'
                },
                {
                    'name': 'league',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID de la liga'
                },
                {
                    'name': 'bet',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID de la apuesta'
                }
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=odds_live_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{odds_live_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{odds_live_endpoint.name}" ya existe')
        
        # Endpoint de cuotas en vivo - tipos de apuestas
        odds_live_bets_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Tipos de Apuestas en Vivo',
            endpoint='odds/live/bets',
            description='Obtiene todas las apuestas disponibles para cuotas en vivo. Los IDs de apuestas pueden usarse como filtros en el endpoint odds/live',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{odds_live_bets_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para tipos de apuestas en vivo
            parameters = [
                {
                    'name': 'id',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'El ID del tipo de apuesta'
                },
                {
                    'name': 'search',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'El nombre del tipo de apuesta (mínimo 3 caracteres)'
                }
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=odds_live_bets_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{odds_live_bets_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{odds_live_bets_endpoint.name}" ya existe')
        




        # 1. Endpoint Odds (Pre-Match)
        odds_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Cuotas Pre-Partido',
            endpoint='odds',
            description='Obtiene cuotas de partidos, ligas o fechas. Proporciona cuotas pre-partido entre 1 y 14 días antes del partido. Actualización cada 3 horas.',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{odds_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para cuotas pre-partido
            parameters = [
                {
                    'name': 'fixture',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del partido'
                },
                {
                    'name': 'league',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID de la liga'
                },
                {
                    'name': 'season',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'La temporada de la liga (formato YYYY)'
                },
                {
                    'name': 'date',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'Una fecha válida (formato YYYY-MM-DD)'
                },
                {
                    'name': 'timezone',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'Una zona horaria válida del endpoint Timezone'
                },
                {
                    'name': 'page',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'Número de página para paginación (predeterminado: 1)'
                },
                {
                    'name': 'bookmaker',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del corredor de apuestas'
                },
                {
                    'name': 'bet',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del tipo de apuesta'
                }
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=odds_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{odds_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{odds_endpoint.name}" ya existe')
            
        # 2. Endpoint Odds Mapping (Pre-Match)
        odds_mapping_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Mapeo de Cuotas',
            endpoint='odds/mapping',
            description='Obtiene la lista de IDs de partidos disponibles para el endpoint de cuotas. Todos los partidos, ligas y fechas pueden usarse como filtros. Actualización diaria.',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{odds_mapping_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para mapeo de cuotas
            parameters = [
                {
                    'name': 'page',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'Número de página para paginación (predeterminado: 1)'
                }
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=odds_mapping_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{odds_mapping_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{odds_mapping_endpoint.name}" ya existe')
            
        # 3. Endpoint Odds Bookmakers (Pre-Match)
        odds_bookmakers_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Corredores de Apuestas',
            endpoint='odds/bookmakers',
            description='Obtiene todos los corredores de apuestas disponibles. Los IDs se pueden usar como filtros en el endpoint odds. Actualización varias veces por semana.',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{odds_bookmakers_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para corredores de apuestas
            parameters = [
                {
                    'name': 'id',
                    'parameter_type': 'integer',
                    'required': False,
                    'description': 'El ID del corredor de apuestas'
                },
                {
                    'name': 'search',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'El nombre del corredor de apuestas (mínimo 3 caracteres)'
                }
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=odds_bookmakers_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{odds_bookmakers_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{odds_bookmakers_endpoint.name}" ya existe')
            
        # 4. Endpoint Odds Bets (Pre-Match)
        odds_bets_endpoint, created = APIEndpoint.objects.get_or_create(
            name='Tipos de Apuestas',
            endpoint='odds/bets',
            description='Obtiene todos los tipos de apuestas disponibles para cuotas pre-partido. Los IDs se pueden usar como filtros en el endpoint odds. Actualización varias veces por semana.',
            has_parameters=True
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Endpoint "{odds_bets_endpoint.name}" creado correctamente'))
            
            # Crear parámetros para tipos de apuestas
            parameters = [
                {
                    'name': 'id',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'El ID del tipo de apuesta'
                },
                {
                    'name': 'search',
                    'parameter_type': 'string',
                    'required': False,
                    'description': 'El nombre del tipo de apuesta (mínimo 3 caracteres)'
                }
            ]
            
            for param_data in parameters:
                param, param_created = APIParameter.objects.get_or_create(
                    endpoint=odds_bets_endpoint,
                    name=param_data['name'],
                    defaults={
                        'parameter_type': param_data['parameter_type'],
                        'required': param_data['required'],
                        'description': param_data['description']
                    }
                )
                
                if param_created:
                    self.stdout.write(f'  - Parámetro "{param.name}" creado para "{odds_bets_endpoint.name}"')
        else:
            self.stdout.write(f'Endpoint "{odds_bets_endpoint.name}" ya existe')
        
        self.stdout.write(self.style.SUCCESS('¡Carga de endpoints completada!'))