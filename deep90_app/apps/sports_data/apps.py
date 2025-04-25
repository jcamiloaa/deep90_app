from django.apps import AppConfig


class SportsDataConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'deep90_app.apps.sports_data'
    
    def ready(self):
        """Ejecutar tareas de inicialización cuando se carga la aplicación"""
        from django.conf import settings
        
        # Solo registrar tareas periódicas en el servidor principal (no en procesos adicionales)
        if not settings.DEBUG or settings.DEBUG and getattr(settings, 'REGISTER_TASKS_IN_DEBUG', True):
            self.register_live_tasks()
    
    def register_live_tasks(self):
        """Registra las tareas periódicas de live football data"""
        try:
            from .live_tasks import register_periodic_live_tasks
            
            # Ejecutar la tarea de registro de manera sincrónica para garantizar que se ejecute al inicio
            register_periodic_live_tasks()
            
        except Exception as e:
            # Capturar cualquier excepción durante el registro para evitar que falle la carga de la aplicación
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error al registrar tareas periódicas de live football: {str(e)}")