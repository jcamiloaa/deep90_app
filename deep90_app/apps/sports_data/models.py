from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
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


class FixtureData(models.Model):
    """Modelo para almacenar datos estructurados de respuestas del endpoint fixtures."""
    result = models.ForeignKey(
        APIResult,
        on_delete=models.CASCADE,
        related_name='fixture_data',
        verbose_name=_("Resultado API")
    )
    query_date = models.DateTimeField(_("Fecha de consulta"), default=timezone.now)
    fixture_id = models.IntegerField(_("ID del partido"))
    date = models.DateTimeField(_("Fecha del partido"))
    timestamp = models.BigIntegerField(_("Timestamp"))
    timezone = models.CharField(_("Zona horaria"), max_length=50)
    status_long = models.CharField(_("Estado (texto)"), max_length=100)
    status_short = models.CharField(_("Estado (abreviado)"), max_length=10)
    elapsed = models.IntegerField(_("Minutos transcurridos"), null=True, blank=True)
    venue_name = models.CharField(_("Estadio"), max_length=255, null=True, blank=True)
    venue_city = models.CharField(_("Ciudad"), max_length=255, null=True, blank=True)
    venue_id = models.IntegerField(_("ID estadio"), null=True, blank=True)
    
    # Equipo local
    home_team_id = models.IntegerField(_("ID equipo local"))
    home_team_name = models.CharField(_("Equipo local"), max_length=255)
    home_team_logo = models.URLField(_("Logo equipo local"), max_length=255, null=True, blank=True)
    home_team_winner = models.BooleanField(_("Ganador local"), null=True, blank=True)
    
    # Equipo visitante
    away_team_id = models.IntegerField(_("ID equipo visitante"))
    away_team_name = models.CharField(_("Equipo visitante"), max_length=255)
    away_team_logo = models.URLField(_("Logo equipo visitante"), max_length=255, null=True, blank=True)
    away_team_winner = models.BooleanField(_("Ganador visitante"), null=True, blank=True)
    
    # Goles
    home_goals = models.IntegerField(_("Goles local"), null=True, blank=True)
    away_goals = models.IntegerField(_("Goles visitante"), null=True, blank=True)
    
    # Puntuación
    home_halftime = models.IntegerField(_("Goles local medio tiempo"), null=True, blank=True)
    away_halftime = models.IntegerField(_("Goles visitante medio tiempo"), null=True, blank=True)
    home_fulltime = models.IntegerField(_("Goles local tiempo completo"), null=True, blank=True)
    away_fulltime = models.IntegerField(_("Goles visitante tiempo completo"), null=True, blank=True)
    home_extratime = models.IntegerField(_("Goles local tiempo extra"), null=True, blank=True)
    away_extratime = models.IntegerField(_("Goles visitante tiempo extra"), null=True, blank=True)
    home_penalty = models.IntegerField(_("Penaltis local"), null=True, blank=True)
    away_penalty = models.IntegerField(_("Penaltis visitante"), null=True, blank=True)
    
    # Liga
    league_id = models.IntegerField(_("ID liga"))
    league_name = models.CharField(_("Liga"), max_length=255)
    league_country = models.CharField(_("País"), max_length=100)
    league_logo = models.URLField(_("Logo liga"), max_length=255, null=True, blank=True)
    league_flag = models.URLField(_("Bandera país"), max_length=255, null=True, blank=True)
    league_season = models.IntegerField(_("Temporada"))
    league_round = models.CharField(_("Jornada"), max_length=100, blank=True)
    
    class Meta:
        verbose_name = _("Datos de Partido")
        verbose_name_plural = _("Datos de Partidos")
        indexes = [
            models.Index(fields=['fixture_id']),
            models.Index(fields=['date']),
            models.Index(fields=['home_team_id']),
            models.Index(fields=['away_team_id']),
            models.Index(fields=['league_id']),
        ]
    
    def __str__(self):
        return f"{self.home_team_name} vs {self.away_team_name} ({self.date})"


class LeagueData(models.Model):
    """Modelo para almacenar datos estructurados de respuestas del endpoint leagues."""
    result = models.ForeignKey(
        APIResult,
        on_delete=models.CASCADE,
        related_name='league_data',
        verbose_name=_("Resultado API")
    )
    league_id = models.IntegerField(_("ID liga"))
    name = models.CharField(_("Nombre"), max_length=255)
    type = models.CharField(_("Tipo"), max_length=50)  # league o cup
    logo = models.URLField(_("Logo"), max_length=255, null=True, blank=True)
    country = models.CharField(_("País"), max_length=100)
    country_code = models.CharField(_("Código país"), max_length=10, null=True, blank=True)
    flag = models.URLField(_("Bandera"), max_length=255, null=True, blank=True)
    season = models.IntegerField(_("Temporada"), null=True, blank=True)
    season_start = models.DateField(_("Inicio temporada"), null=True, blank=True)
    season_end = models.DateField(_("Fin temporada"), null=True, blank=True)
    standings = models.BooleanField(_("Tiene clasificaciones"), default=False)
    is_current = models.BooleanField(_("Temporada actual"), default=False)
    
    class Meta:
        verbose_name = _("Datos de Liga")
        verbose_name_plural = _("Datos de Ligas")
        indexes = [
            models.Index(fields=['league_id']),
            models.Index(fields=['country']),
            models.Index(fields=['season']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.country})"


class StandingData(models.Model):
    """Modelo para almacenar datos estructurados de respuestas del endpoint standings."""
    result = models.ForeignKey(
        APIResult,
        on_delete=models.CASCADE,
        related_name='standing_data',
        verbose_name=_("Resultado API")
    )
    league_id = models.IntegerField(_("ID liga"))
    league_name = models.CharField(_("Liga"), max_length=255)
    season = models.IntegerField(_("Temporada"))
    team_id = models.IntegerField(_("ID equipo"))
    team_name = models.CharField(_("Equipo"), max_length=255)
    team_logo = models.URLField(_("Logo equipo"), max_length=255, null=True, blank=True)
    rank = models.IntegerField(_("Posición"))
    group = models.CharField(_("Grupo"), max_length=50, null=True, blank=True)
    form = models.CharField(_("Forma"), max_length=20, null=True, blank=True)
    played = models.IntegerField(_("Jugados"))
    win = models.IntegerField(_("Ganados"))
    draw = models.IntegerField(_("Empatados"))
    lose = models.IntegerField(_("Perdidos"))
    goals_for = models.IntegerField(_("Goles a favor"))
    goals_against = models.IntegerField(_("Goles en contra"))
    goals_diff = models.IntegerField(_("Diferencia de goles"))
    points = models.IntegerField(_("Puntos"))
    description = models.CharField(_("Descripción"), max_length=255, null=True, blank=True)
    
    class Meta:
        verbose_name = _("Datos de Clasificación")
        verbose_name_plural = _("Datos de Clasificaciones")
        indexes = [
            models.Index(fields=['team_id']),
            models.Index(fields=['league_id']),
            models.Index(fields=['season']),
        ]
    
    def __str__(self):
        return f"{self.team_name} - {self.league_name} (Pos. {self.rank})"