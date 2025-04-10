import os
from django.core.management.base import BaseCommand
from deep90_app.apps.sports_data.models import APIEndpoint, APIParameter


class Command(BaseCommand):
    help = 'Carga endpoints iniciales para la API de fútbol'

    def handle(self, *args, **kwargs):
        self.stdout.write('Cargando endpoints iniciales para la API de fútbol...')
        
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
        
        # Añade más endpoints aquí si es necesario...
        
        self.stdout.write(self.style.SUCCESS('¡Carga de endpoints completada!'))