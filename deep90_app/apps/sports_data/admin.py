from django.contrib import admin
from .models import APIEndpoint, APIParameter, ScheduledTask, APIResult, FixtureData, LeagueData, StandingData


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
    list_display = ['league_id', 'name', 'country', 'season', 'type', 'is_current']
    list_filter = ['country', 'type', 'is_current']
    search_fields = ['name', 'country']
    readonly_fields = ['result']


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