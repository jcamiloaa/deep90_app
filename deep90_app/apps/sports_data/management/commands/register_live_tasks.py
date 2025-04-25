from django.core.management.base import BaseCommand
from django.utils import timezone
from deep90_app.apps.sports_data.live_tasks import register_periodic_live_tasks, monitor_live_tasks


class Command(BaseCommand):
    help = 'Registra y/o reinicia las tareas periódicas para los datos de fútbol en vivo'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force-run',
            action='store_true',
            help='Forzar la ejecución inmediata del monitor de tareas en vivo'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(f'Iniciando registro de tareas periódicas a las {timezone.now()}'))
        
        # Registrar tareas periódicas
        result = register_periodic_live_tasks()
        
        self.stdout.write(self.style.SUCCESS('Tareas periódicas registradas correctamente:'))
        self.stdout.write(f"  Monitor: cada {result['config']['monitor_interval']} segundos")
        self.stdout.write(f"  Partidos en vivo: cada {result['config']['fixture_interval']} segundos")
        self.stdout.write(f"  Cuotas en vivo: cada {result['config']['odds_interval']} segundos")
        
        if options['force_run']:
            self.stdout.write(self.style.WARNING('Forzando ejecución del monitor...'))
            monitor_result = monitor_live_tasks()
            
            if monitor_result['fixture_tasks_run'] or monitor_result['odds_tasks_run']:
                self.stdout.write(self.style.SUCCESS('Monitor ejecutado, se iniciaron las siguientes tareas:'))
                if monitor_result['fixture_tasks_run']:
                    self.stdout.write(f"  Partidos: {', '.join(monitor_result['fixture_tasks_run'])}")
                if monitor_result['odds_tasks_run']:
                    self.stdout.write(f"  Cuotas: {', '.join(monitor_result['odds_tasks_run'])}")
            else:
                self.stdout.write(self.style.WARNING('Monitor ejecutado, pero no se encontraron tareas que ejecutar.'))
        
        self.stdout.write(self.style.SUCCESS('Proceso completado.'))