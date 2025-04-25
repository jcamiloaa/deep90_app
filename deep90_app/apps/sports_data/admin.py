from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse, path
from django.http import JsonResponse
from .models import (
    APIEndpoint, APIParameter, ScheduledTask, APIResult, 
    FixtureData, LeagueData, StandingData,
    LiveFixtureTask, LiveFixtureData, LiveOddsTask, LiveOddsData,
    LiveOddsCategory, LiveOddsValue
)
from .live_tasks import toggle_task_status, restart_task


@admin.register(APIEndpoint)
class APIEndpointAdmin(admin.ModelAdmin):
    list_display = ['name', 'endpoint', 'has_parameters']
    list_filter = ['has_parameters']
    search_fields = ['name', 'endpoint', 'description']


@admin.register(APIParameter)
class APIParameterAdmin(admin.ModelAdmin):
    list_display = ['name', 'endpoint', 'parameter_type', 'required']
    list_filter = ['parameter_type', 'required', 'endpoint']
    search_fields = ['name', 'description']


@admin.register(ScheduledTask)
class ScheduledTaskAdmin(admin.ModelAdmin):
    list_display = ['name', 'endpoint', 'created_by', 'created_at', 'status', 'schedule_type']
    list_filter = ['status', 'schedule_type', 'endpoint']
    search_fields = ['name', 'created_by__username']
    readonly_fields = ['created_at', 'celery_task_id']
    

@admin.register(APIResult)
class APIResultAdmin(admin.ModelAdmin):
    list_display = ['task', 'executed_at', 'response_code', 'success', 'execution_time']
    list_filter = ['success', 'response_code']
    search_fields = ['task__name', 'error_message']
    readonly_fields = ['executed_at', 'execution_time']
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # En modo edición
            return self.readonly_fields + ['task', 'response_code', 'response_data', 'execution_time', 'success', 'error_message']
        return self.readonly_fields


@admin.register(FixtureData)
class FixtureDataAdmin(admin.ModelAdmin):
    list_display = ['fixture_id', 'home_team_name', 'score', 'away_team_name', 'date', 'status_long', 'league_name', 'query_date']
    list_filter = ['status_long', 'league_name', 'league_country', 'query_date']
    search_fields = ['home_team_name', 'away_team_name', 'league_name', 'venue_name']
    date_hierarchy = 'date'
    readonly_fields = ['result', 'query_date']
    
    def score(self, obj):
        """Mostrar el marcador del partido en formato home_goals - away_goals"""
        if obj.home_goals is not None and obj.away_goals is not None:
            return f"{obj.home_goals} - {obj.away_goals}"
        return "- vs -"
    
    score.short_description = "Marcador"
    
    fieldsets = (
        ('Información básica', {
            'fields': ('result', 'fixture_id', 'date', 'timestamp', 'timezone', 'status_long', 'status_short', 'elapsed', 'query_date')
        }),
        ('Equipos', {
            'fields': (
                ('home_team_id', 'home_team_name', 'home_team_logo', 'home_team_winner'),
                ('away_team_id', 'away_team_name', 'away_team_logo', 'away_team_winner')
            )
        }),
        ('Marcador', {
            'fields': (
                ('home_goals', 'away_goals'),
                ('home_halftime', 'away_halftime'),
                ('home_fulltime', 'away_fulltime'),
                ('home_extratime', 'away_extratime'),
                ('home_penalty', 'away_penalty')
            )
        }),
        ('Sede', {
            'fields': ('venue_id', 'venue_name', 'venue_city')
        }),
        ('Liga', {
            'fields': ('league_id', 'league_name', 'league_country', 'league_season', 'league_round', 'league_logo', 'league_flag')
        })
    )


@admin.register(LeagueData)
class LeagueDataAdmin(admin.ModelAdmin):
    list_display = ['league_id', 'name', 'country', 'season', 'season_start', 'season_end','type', 'is_current']
    list_filter = ['country', 'type', 'is_current', 'season', 'season_start', 'season_end','coverage_fixtures', 'coverage_players', 'coverage_predictions']
    search_fields = ['name', 'country']
    readonly_fields = ['result']
    
    fieldsets = (
        ('Información básica', {
            'fields': ('result', 'league_id', 'name', 'type', 'logo')
        }),
        ('País', {
            'fields': ('country', 'country_code', 'flag')
        }),
        ('Temporada', {
            'fields': ('season', 'season_start', 'season_end', 'is_current', 'standings')
        }),
        ('Cobertura de Partidos', {
            'classes': ('collapse',),
            'fields': (
                'coverage_fixtures',
                'coverage_fixtures_events',
                'coverage_fixtures_lineups',
                'coverage_fixtures_statistics_fixtures',
                'coverage_fixtures_statistics_players',
            )
        }),
        ('Cobertura de Jugadores', {
            'classes': ('collapse',),
            'fields': (
                'coverage_players',
                'coverage_top_scorers',
                'coverage_top_assists',
                'coverage_top_cards',
                'coverage_injuries',
            )
        }),
        ('Otras Coberturas', {
            'classes': ('collapse',),
            'fields': ('coverage_predictions', 'coverage_odds')
        }),
    )


@admin.register(StandingData)
class StandingDataAdmin(admin.ModelAdmin):
    list_display = ['team_name', 'rank', 'league_name', 'season', 'played', 'points', 'goals_diff']
    list_filter = ['league_name', 'season']
    search_fields = ['team_name', 'league_name']
    readonly_fields = ['result']
    
    fieldsets = (
        ('Información básica', {
            'fields': ('result', 'team_id', 'team_name', 'team_logo')
        }),
        ('Liga', {
            'fields': ('league_id', 'league_name', 'season', 'group')
        }),
        ('Posición', {
            'fields': ('rank', 'points', 'description', 'form')
        }),
        ('Estadísticas', {
            'fields': (
                ('played', 'win', 'draw', 'lose'),
                ('goals_for', 'goals_against', 'goals_diff')
            )
        })
    )


# Admin para tareas y datos nativos en vivo

class LiveTaskAdminBase(admin.ModelAdmin):
    """Clase base para administradores de tareas en vivo"""
    list_display = ['name', 'status_display', 'is_enabled', 'interval_seconds', 'last_run', 'next_run', 'error_count']
    list_filter = ['status', 'is_enabled']
    search_fields = ['name', 'description']
    readonly_fields = ['last_run', 'next_run', 'last_error', 'error_count', 'status', 'created_at', 'created_by', 'celery_task_id']
    
    fieldsets = (
        ('Información básica', {
            'fields': ('name', 'description', 'is_enabled')
        }),
        ('Configuración', {
            'fields': ('interval_seconds',)
        }),
        ('Estado actual', {
            'fields': ('status', 'last_run', 'next_run', 'error_count', 'last_error')
        }),
        ('Información del sistema', {
            'fields': ('created_by', 'created_at', 'celery_task_id')
        }),
    )
    
    def status_display(self, obj):
        """Muestra el estado de la tarea con formato HTML para colores según el estado"""
        status_colors = {
            'idle': 'blue',
            'running': 'green',
            'failed': 'red',
            'paused': 'orange',
        }
        color = status_colors.get(obj.status, 'black')
        enabled = "✓" if obj.is_enabled else "✗"
        return format_html('<span style="color: {};"><strong>{}</strong></span> [{}]', 
                           color, obj.get_status_display(), enabled)
    
    status_display.short_description = "Estado"
    
    def get_urls(self):
        """Añade URLs personalizadas para acciones AJAX en el admin"""
        urls = super().get_urls()
        custom_urls = [
            path('toggle-status/<int:task_id>/', 
                self.admin_site.admin_view(self.toggle_status),
                name=f'{self.task_type}-toggle-status'),
            path('restart-task/<int:task_id>/',
                self.admin_site.admin_view(self.restart_task_view),
                name=f'{self.task_type}-restart-task'),
        ]
        return custom_urls + urls
    
    def toggle_status(self, request, task_id):
        """Vista para activar/desactivar una tarea vía AJAX"""
        result = toggle_task_status(self.task_type, task_id)
        return JsonResponse(result)
    
    def restart_task_view(self, request, task_id):
        """Vista para reiniciar una tarea fallida vía AJAX"""
        result = restart_task(self.task_type, task_id)
        return JsonResponse(result)
    
    class Media:
        js = ('js/live_tasks_admin.js',)


@admin.register(LiveFixtureTask)
class LiveFixtureTaskAdmin(LiveTaskAdminBase):
    """Admin para tareas de partidos en vivo"""
    task_type = 'fixture'


@admin.register(LiveOddsTask)
class LiveOddsTaskAdmin(LiveTaskAdminBase):
    """Admin para tareas de cuotas en vivo"""
    task_type = 'odds'


@admin.register(LiveFixtureData)
class LiveFixtureDataAdmin(admin.ModelAdmin):
    """Admin para datos de partidos en vivo"""
    list_display = ['fixture_id', 'home_team_name', 'live_score', 'away_team_name', 'elapsed_display', 'status_display', 'league_name', 'updated_at']
    list_filter = ['status_short', 'league_name', 'league_country']
    search_fields = ['home_team_name', 'away_team_name', 'league_name', 'venue_name']
    readonly_fields = ['task', 'raw_data', 'updated_at']
    
    def live_score(self, obj):
        """Mostrar el marcador del partido con formato HTML para destacar los goles"""
        if obj.home_goals is not None and obj.away_goals is not None:
            return format_html('<strong style="font-size: 1.1em;">{} - {}</strong>', 
                              obj.home_goals, obj.away_goals)
        return format_html('<span style="color: #999;">- vs -</span>')
    
    live_score.short_description = "Marcador"
    
    def elapsed_display(self, obj):
        """Mostrar el tiempo transcurrido con formato"""
        if obj.elapsed:
            if obj.elapsed_seconds:
                return f"{obj.elapsed}:{obj.elapsed_seconds}'"
            return f"{obj.elapsed}'"
        return "-"
    
    elapsed_display.short_description = "Minuto"
    
    def status_display(self, obj):
        """Mostrar el estado del partido con formato HTML para colores según el estado"""
        status_colors = {
            'NS': '#999',      # No iniciado
            '1H': '#00c853',   # Primera parte
            'HT': '#ff9800',   # Descanso
            '2H': '#00c853',   # Segunda parte
            'ET': '#8bc34a',   # Tiempo extra
            'BT': '#ff9800',   # Pausa
            'P': '#8bc34a',    # Penaltis
            'FT': '#2196f3',   # Finalizado
            'AET': '#2196f3',  # Finalizado en prórroga
            'PEN': '#2196f3',  # Finalizado en penaltis
        }
        color = status_colors.get(obj.status_short, '#999')
        return format_html('<span style="color: {};"><strong>{}</strong></span>', 
                          color, obj.status_long)
    
    status_display.short_description = "Estado"
    
    fieldsets = (
        ('Información básica', {
            'fields': ('task', 'fixture_id', 'date', 'timezone', 'status_long', 'status_short', 'elapsed', 'elapsed_seconds', 'updated_at')
        }),
        ('Equipos y marcador', {
            'fields': (
                ('home_team_name', 'home_goals', 'home_team_winner'),
                ('away_team_name', 'away_goals', 'away_team_winner'),
            )
        }),
        ('Detalles del marcador', {
            'fields': (
                ('home_halftime', 'away_halftime'),
                ('home_fulltime', 'away_fulltime'),
                ('home_extratime', 'away_extratime'),
                ('home_penalty', 'away_penalty')
            )
        }),
        ('Sede', {
            'fields': ('venue_name', 'venue_city', 'referee')
        }),
        ('Liga', {
            'fields': ('league_id', 'league_name', 'league_country', 'league_season', 'league_round')
        }),
        ('Datos en bruto', {
            'classes': ('collapse',),
            'fields': ('raw_data',)
        }),
    )


@admin.register(LiveOddsData)
class LiveOddsDataAdmin(admin.ModelAdmin):
    """Admin para datos de cuotas en vivo"""
    list_display = ['fixture_id', 'teams_display', 'status_elapsed', 'odds_status_display', 'updated_at']
    list_filter = ['is_blocked', 'is_stopped', 'is_finished']
    search_fields = ['fixture_id']
    readonly_fields = ['task', 'raw_odds_data', 'update_time', 'updated_at']
    
    def teams_display(self, obj):
        """Mostrar información del partido con marcador"""
        if obj.home_goals is not None and obj.away_goals is not None:
            return f"ID: {obj.fixture_id} ({obj.home_goals} - {obj.away_goals})"
        return f"ID: {obj.fixture_id}"
    
    teams_display.short_description = "Partido"
    
    def odds_status_display(self, obj):
        """Mostrar estado de las cuotas con formato HTML"""
        statuses = []
        
        if obj.is_blocked:
            statuses.append(format_html('<span style="color: #e53935;">Bloqueado</span>'))
        
        if obj.is_stopped:
            statuses.append(format_html('<span style="color: #ff9800;">Detenido</span>'))
            
        if obj.is_finished:
            statuses.append(format_html('<span style="color: #2196f3;">Finalizado</span>'))
            
        if not statuses:
            return format_html('<span style="color: #00c853;">Activo</span>')
            
        return format_html(', '.join(s for s in statuses))
    
    odds_status_display.short_description = "Estado"
    
    def category_count(self, obj):
        """Mostrar el número de categorías de cuotas"""
        return obj.odds_categories.count()
    
    category_count.short_description = "Categorías"
    
    fieldsets = (
        ('Información básica', {
            'fields': ('task', 'fixture_id', 'league_id', 'league_season', 'updated_at', 'update_time')
        }),
        ('Estado del partido', {
            'fields': (
                ('home_team_id', 'away_team_id'),
                ('home_goals', 'away_goals'),
                ('status_elapsed', 'status_elapsed_seconds', 'status_long')
            )
        }),
        ('Estado de apuestas', {
            'fields': (
                ('is_blocked', 'is_stopped', 'is_finished'),
            )
        }),
        ('Datos en bruto', {
            'classes': ('collapse',),
            'fields': ('raw_odds_data',)
        }),
    )
    
    def get_list_display(self, request):
        """Añadir contador de categorías al listado"""
        return self.list_display + ['category_count']


class LiveOddsValueInline(admin.TabularInline):
    """Inline para valores de cuotas"""
    model = LiveOddsValue
    extra = 0
    fields = ['value', 'odd', 'handicap', 'suspended', 'main']
    readonly_fields = ['updated_at']
    can_delete = False
    

@admin.register(LiveOddsCategory)
class LiveOddsCategoryAdmin(admin.ModelAdmin):
    """Admin para categorías de cuotas en vivo"""
    list_display = ['name', 'fixture_id_display', 'values_count', 'updated_at']
    list_filter = ['name','odds_data__fixture_id']
    search_fields = ['name', 'odds_data__fixture_id']
    readonly_fields = ['odds_data', 'category_id', 'updated_at']
    inlines = [LiveOddsValueInline]
    
    def fixture_id_display(self, obj):
        """Mostrar el ID del partido"""
        return f"Partido: {obj.odds_data.fixture_id}"
    
    fixture_id_display.short_description = "Partido"
    
    def values_count(self, obj):
        """Mostrar el número de valores de cuotas"""
        return obj.values.count()
    
    values_count.short_description = "Valores"


@admin.register(LiveOddsValue)
class LiveOddsValueAdmin(admin.ModelAdmin):
    """Admin para valores de cuotas individuales"""
    list_display = ['value_display', 'category_name', 'odd', 'handicap', 'suspended_display', 'updated_at']
    list_filter = ['suspended', 'category__name']
    search_fields = ['value', 'category__name', 'category__odds_data__fixture_id']
    readonly_fields = ['category', 'updated_at']
    
    def value_display(self, obj):
        """Mostrar el valor de la cuota con formato HTML"""
        if obj.suspended:
            return format_html('<span style="color: #999; text-decoration: line-through;">{}</span>', obj.value)
        return obj.value
    
    value_display.short_description = "Valor"
    
    def category_name(self, obj):
        """Mostrar el nombre de la categoría"""
        return obj.category.name
    
    category_name.short_description = "Categoría"
    
    def suspended_display(self, obj):
        """Mostrar si la cuota está suspendida con formato HTML"""
        if obj.suspended:
            return format_html('<span style="color: #e53935;">✓</span>')
        return format_html('<span style="color: #00c853;">✗</span>')
    
    suspended_display.short_description = "Suspendido"