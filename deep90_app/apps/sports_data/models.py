from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
import json

User = get_user_model()

class APIEndpoint(models.Model):
    """Modelo para representar los endpoints disponibles de la API."""
    name = models.CharField(_("Nombre"), max_length=100)
    endpoint = models.CharField(_("Endpoint"), max_length=200)
    description = models.TextField(_("Descripción"), blank=True)
    has_parameters = models.BooleanField(_("Tiene parámetros"), default=False)
    
    class Meta:
        verbose_name = _("Endpoint API")
        verbose_name_plural = _("Endpoints API")
    
    def __str__(self):
        return f"{self.name} ({self.endpoint})"


class APIParameter(models.Model):
    """Modelo para representar los posibles parámetros de los endpoints."""
    PARAMETER_TYPES = (
        ('integer', _('Entero')),
        ('string', _('Texto')),
        ('boolean', _('Booleano')),
    )
    
    endpoint = models.ForeignKey(
        APIEndpoint, 
        on_delete=models.CASCADE, 
        related_name='parameters',
        verbose_name=_("Endpoint")
    )
    name = models.CharField(_("Nombre"), max_length=100)
    parameter_type = models.CharField(
        _("Tipo de parámetro"), 
        max_length=20, 
        choices=PARAMETER_TYPES
    )
    required = models.BooleanField(_("Requerido"), default=False)
    description = models.TextField(_("Descripción"), blank=True)
    
    class Meta:
        verbose_name = _("Parámetro API")
        verbose_name_plural = _("Parámetros API")
    
    def __str__(self):
        return f"{self.name} ({self.get_parameter_type_display()})"


class ScheduledTask(models.Model):
    """Modelo para representar tareas programadas para llamar a la API."""
    STATUS_CHOICES = (
        ('pending', _('Pendiente')),
        ('running', _('En ejecución')),
        ('success', _('Completado')),
        ('failed', _('Fallido')),
        ('cancelled', _('Cancelado')),
    )
    
    SCHEDULE_TYPE_CHOICES = (
        ('immediate', _('Inmediata')),
        ('scheduled', _('Programada')),
        ('periodic', _('Periódica')),
    )
    
    name = models.CharField(_("Nombre"), max_length=200)
    endpoint = models.ForeignKey(
        APIEndpoint, 
        on_delete=models.CASCADE,
        related_name='tasks',
        verbose_name=_("Endpoint")
    )
    parameters = models.JSONField(_("Parámetros"), blank=True, null=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='created_tasks',
        verbose_name=_("Creado por")
    )
    created_at = models.DateTimeField(_("Fecha de creación"), auto_now_add=True)
    scheduled_time = models.DateTimeField(_("Fecha programada"), blank=True, null=True)
    status = models.CharField(_("Estado"), max_length=20, choices=STATUS_CHOICES, default='pending')
    schedule_type = models.CharField(
        _("Tipo de programación"), 
        max_length=20, 
        choices=SCHEDULE_TYPE_CHOICES,
        default='immediate'
    )
    periodic_interval = models.PositiveIntegerField(
        _("Intervalo periódico (minutos)"), 
        blank=True, 
        null=True
    )
    celery_task_id = models.CharField(_("ID tarea Celery"), max_length=100, blank=True, null=True)
    
    class Meta:
        verbose_name = _("Tarea programada")
        verbose_name_plural = _("Tareas programadas")
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.endpoint.name})"

    def get_parameters_display(self):
        if not self.parameters:
            return "Sin parámetros"
        params = []
        for key, value in self.parameters.items():
            params.append(f"{key}: {value}")
        return ", ".join(params)


class APIResult(models.Model):
    """Modelo para almacenar los resultados de las llamadas a la API."""
    task = models.ForeignKey(
        ScheduledTask, 
        on_delete=models.CASCADE,
        related_name='results',
        verbose_name=_("Tarea")
    )
    executed_at = models.DateTimeField(_("Fecha de ejecución"), auto_now_add=True)
    response_code = models.IntegerField(_("Código de respuesta"))
    response_data = models.JSONField(_("Datos de respuesta"), blank=True, null=True)
    execution_time = models.FloatField(_("Tiempo de ejecución (seg)"), blank=True, null=True)
    success = models.BooleanField(_("Éxito"), default=True)
    error_message = models.TextField(_("Mensaje de error"), blank=True, null=True)
    
    class Meta:
        verbose_name = _("Resultado API")
        verbose_name_plural = _("Resultados API")
        ordering = ['-executed_at']
    
    def __str__(self):
        return f"Resultado {self.id} - Tarea: {self.task.name}"
    
    def get_formatted_response(self):
        """Devuelve los datos de respuesta formateados para mostrar en el admin."""
        if not self.response_data:
            return "Sin datos"
        try:
            return json.dumps(self.response_data, indent=2)
        except Exception:
            return str(self.response_data)