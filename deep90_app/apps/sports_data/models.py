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
    
    # Campos de cobertura
    coverage_fixtures = models.BooleanField(_("Cobertura fixtures"), default=False)
    coverage_fixtures_events = models.BooleanField(_("Cobertura eventos"), default=False)
    coverage_fixtures_lineups = models.BooleanField(_("Cobertura alineaciones"), default=False)
    coverage_fixtures_statistics_players = models.BooleanField(_("Cobertura estadísticas jugadores"), default=False)
    coverage_fixtures_statistics_fixtures = models.BooleanField(_("Cobertura estadísticas partidos"), default=False)
    coverage_players = models.BooleanField(_("Cobertura jugadores"), default=False)
    coverage_top_scorers = models.BooleanField(_("Cobertura goleadores"), default=False)
    coverage_top_assists = models.BooleanField(_("Cobertura asistencias"), default=False)
    coverage_top_cards = models.BooleanField(_("Cobertura tarjetas"), default=False)
    coverage_injuries = models.BooleanField(_("Cobertura lesiones"), default=False)
    coverage_predictions = models.BooleanField(_("Cobertura predicciones"), default=False)
    coverage_odds = models.BooleanField(_("Cobertura apuestas"), default=False)
    
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


class LiveFixtureTask(models.Model):
    """Modelo para representar tareas nativas del sistema para obtener partidos en vivo."""
    STATUS_CHOICES = (
        ('idle', _('Inactivo')),
        ('running', _('En ejecución')),
        ('failed', _('Fallido')),
        ('paused', _('Pausado')),
    )
    
    name = models.CharField(_("Nombre"), max_length=200)
    description = models.TextField(_("Descripción"), blank=True)
    status = models.CharField(_("Estado"), max_length=20, choices=STATUS_CHOICES, default='idle')
    is_enabled = models.BooleanField(_("Habilitado"), default=True)
    interval_seconds = models.PositiveIntegerField(
        _("Intervalo de actualización (segundos)"), 
        default=60,
        help_text=_("Recomendado: 60 segundos para partidos en vivo")
    )
    last_run = models.DateTimeField(_("Última ejecución"), null=True, blank=True)
    next_run = models.DateTimeField(_("Próxima ejecución"), null=True, blank=True)
    created_at = models.DateTimeField(_("Fecha de creación"), auto_now_add=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='live_fixture_tasks',
        verbose_name=_("Creado por")
    )
    celery_task_id = models.CharField(_("ID tarea Celery"), max_length=100, blank=True, null=True)
    last_error = models.TextField(_("Último error"), blank=True, null=True)
    error_count = models.PositiveIntegerField(_("Contador de errores"), default=0)
    
    class Meta:
        verbose_name = _("Tarea de partidos en vivo")
        verbose_name_plural = _("Live_Tareas de partidos en vivo")
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"
    
    def reset_errors(self):
        """Reinicia los contadores de error."""
        self.error_count = 0
        self.last_error = None
        self.save(update_fields=['error_count', 'last_error'])
        
    def update_status(self, status, error=None):
        """Actualiza el estado de la tarea y registra errores si los hay."""
        self.status = status
        if error:
            self.last_error = str(error)
            self.error_count += 1
        self.save(update_fields=['status', 'last_error', 'error_count'])


class LiveFixtureData(models.Model):
    """Modelo para almacenar datos de partidos en vivo."""
    task = models.ForeignKey(
        LiveFixtureTask,
        on_delete=models.CASCADE,
        related_name='fixtures',
        verbose_name=_("Tarea")
    )
    fixture_id = models.IntegerField(_("ID del partido"))
    date = models.DateTimeField(_("Fecha del partido"))
    timestamp = models.BigIntegerField(_("Timestamp"))
    timezone = models.CharField(_("Zona horaria"), max_length=50)
    status_long = models.CharField(_("Estado (texto)"), max_length=100)
    status_short = models.CharField(_("Estado (abreviado)"), max_length=10)
    elapsed = models.IntegerField(_("Minutos transcurridos"), null=True, blank=True)
    elapsed_seconds = models.IntegerField(_("Segundos adicionales"), null=True, blank=True)
    venue_name = models.CharField(_("Estadio"), max_length=255, null=True, blank=True)
    venue_city = models.CharField(_("Ciudad"), max_length=255, null=True, blank=True)
    referee = models.CharField(_("Árbitro"), max_length=255, null=True, blank=True)
    
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
    
    # Datos adicionales
    raw_data = models.JSONField(_("Datos en bruto"), blank=True, null=True)
    updated_at = models.DateTimeField(_("Última actualización"), auto_now=True)
    
    class Meta:
        verbose_name = _("Partido en vivo")
        verbose_name_plural = _("live_Partidos en vivo")
        indexes = [
            models.Index(fields=['fixture_id']),
            models.Index(fields=['date']),
            models.Index(fields=['status_short']),
            models.Index(fields=['league_id']),
        ]
        unique_together = ('task', 'fixture_id')
    
    def __str__(self):
        return f"{self.home_team_name} vs {self.away_team_name} ({self.elapsed}' - {self.status_long})"


class LiveOddsTask(models.Model):
    """Modelo para representar tareas nativas del sistema para obtener cuotas en vivo."""
    STATUS_CHOICES = (
        ('idle', _('Inactivo')),
        ('running', _('En ejecución')),
        ('failed', _('Fallido')),
        ('paused', _('Pausado')),
    )
    
    name = models.CharField(_("Nombre"), max_length=200)
    description = models.TextField(_("Descripción"), blank=True)
    status = models.CharField(_("Estado"), max_length=20, choices=STATUS_CHOICES, default='idle')
    is_enabled = models.BooleanField(_("Habilitado"), default=True)
    interval_seconds = models.PositiveIntegerField(
        _("Intervalo de actualización (segundos)"), 
        default=60,
        help_text=_("Recomendado: 60 segundos para cuotas en vivo")
    )
    last_run = models.DateTimeField(_("Última ejecución"), null=True, blank=True)
    next_run = models.DateTimeField(_("Próxima ejecución"), null=True, blank=True)
    created_at = models.DateTimeField(_("Fecha de creación"), auto_now_add=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='live_odds_tasks',
        verbose_name=_("Creado por")
    )
    celery_task_id = models.CharField(_("ID tarea Celery"), max_length=100, blank=True, null=True)
    last_error = models.TextField(_("Último error"), blank=True, null=True)
    error_count = models.PositiveIntegerField(_("Contador de errores"), default=0)
    
    class Meta:
        verbose_name = _("Tarea de cuotas en vivo")
        verbose_name_plural = _("live_Tareas de cuotas en vivo")
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"
    
    def reset_errors(self):
        """Reinicia los contadores de error."""
        self.error_count = 0
        self.last_error = None
        self.save(update_fields=['error_count', 'last_error'])
        
    def update_status(self, status, error=None):
        """Actualiza el estado de la tarea y registra errores si los hay."""
        self.status = status
        if error:
            self.last_error = str(error)
            self.error_count += 1
        self.save(update_fields=['status', 'last_error', 'error_count'])


class LiveOddsData(models.Model):
    """Modelo para almacenar datos de cuotas en vivo."""
    task = models.ForeignKey(
        LiveOddsTask,
        on_delete=models.CASCADE,
        related_name='odds',
        verbose_name=_("Tarea")
    )
    fixture_id = models.IntegerField(_("ID del partido"))
    league_id = models.IntegerField(_("ID liga"))
    league_season = models.IntegerField(_("Temporada"))
    
    # Equipos y marcador
    home_team_id = models.IntegerField(_("ID equipo local"))
    away_team_id = models.IntegerField(_("ID equipo visitante"))
    home_goals = models.IntegerField(_("Goles local"), null=True, blank=True)
    away_goals = models.IntegerField(_("Goles visitante"), null=True, blank=True)
    
    # Estado del partido
    status_elapsed = models.IntegerField(_("Minutos transcurridos"), null=True, blank=True)
    status_elapsed_seconds = models.IntegerField(_("Segundos adicionales"), null=True, blank=True)
    status_long = models.CharField(_("Estado (texto)"), max_length=100)
    
    # Estado de las apuestas
    is_stopped = models.BooleanField(_("Detenido"), default=False)
    is_blocked = models.BooleanField(_("Bloqueado"), default=False)
    is_finished = models.BooleanField(_("Finalizado"), default=False)
    
    # Datos y actualizaciones
    update_time = models.CharField(_("Hora actualización"), max_length=50)
    raw_odds_data = models.JSONField(_("Datos en bruto de cuotas"), blank=True, null=True)
    updated_at = models.DateTimeField(_("Última actualización"), auto_now=True)
    
    class Meta:
        verbose_name = _("Cuota en vivo")
        verbose_name_plural = _("live_Cuotas en vivo")
        indexes = [
            models.Index(fields=['fixture_id']),
            models.Index(fields=['league_id']),
        ]
        unique_together = ('task', 'fixture_id')
    
    def __str__(self):
        return f"Cuotas partido ID: {self.fixture_id} ({self.status_elapsed}')"


class LiveOddsCategory(models.Model):
    """Modelo para almacenar las categorías de cuotas de apuesta en vivo."""
    odds_data = models.ForeignKey(
        LiveOddsData,
        on_delete=models.CASCADE,
        related_name='odds_categories',
        verbose_name=_("live_Datos de cuotas")
    )
    category_id = models.IntegerField(_("ID de categoría"))
    name = models.CharField(_("Nombre"), max_length=255)
    updated_at = models.DateTimeField(_("Última actualización"), auto_now=True)
    
    class Meta:
        verbose_name = _("Categoría de cuotas")
        verbose_name_plural = _("live_Categorías de cuotas")
        indexes = [
            models.Index(fields=['category_id']),
        ]
        unique_together = ('odds_data', 'category_id')
    
    def __str__(self):
        return f"{self.name} - Partido: {self.odds_data.fixture_id}"


class LiveOddsValue(models.Model):
    """Modelo para almacenar los valores de cuotas específicos para cada categoría."""
    category = models.ForeignKey(
        LiveOddsCategory,
        on_delete=models.CASCADE,
        related_name='values',
        verbose_name=_("Categoría")
    )
    value = models.CharField(_("Valor"), max_length=255)
    odd = models.CharField(_("Cuota"), max_length=50)
    handicap = models.CharField(_("Handicap"), max_length=50, null=True, blank=True)
    main = models.BooleanField(_("Principal"), null=True, blank=True)
    suspended = models.BooleanField(_("Suspendido"), default=False)
    updated_at = models.DateTimeField(_("Última actualización"), auto_now=True)
    
    class Meta:
        verbose_name = _("Valor de cuota")
        verbose_name_plural = _("live_Valores de cuotas")
        unique_together = ('category', 'value', 'handicap')
    
    def __str__(self):
        return f"{self.category.name}: {self.value} ({self.odd})"