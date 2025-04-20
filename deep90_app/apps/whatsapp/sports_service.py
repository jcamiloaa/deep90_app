import logging
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q
from deep90_app.apps.sports_data.models import FixtureData, LeagueData, StandingData
from collections import defaultdict

logger = logging.getLogger(__name__)

class FootballDataService:
    """Servicio para consultar datos de fútbol de la base de datos."""
    
    def get_upcoming_fixtures(self, days=3, limit=5, league_id=None):
        """
        Obtener los próximos partidos.
        
        Args:
            days: Número de días hacia adelante para buscar
            limit: Límite de resultados
            league_id: ID de la liga (opcional para filtrar)
            
        Returns:
            Lista de partidos próximos
        """
        try:
            now = timezone.now()
            future_date = now + timedelta(days=days)
            
            query = Q(date__gte=now, date__lte=future_date)
            
            if league_id:
                query &= Q(league_id=league_id)
                
            fixtures = FixtureData.objects.filter(query).order_by('date')[:limit]
            return fixtures
        except Exception as e:
            logger.error(f"Error obteniendo próximos partidos: {e}")
            return []
    
    def get_live_match_results(self, limit=5):
        """
        Obtener los partidos que se están jugando en este momento.
        
        Args:
            limit: Límite de resultados
            
        Returns:
            Lista de partidos en vivo
        """
        try:
            # Los partidos en vivo tienen status_short NS (Not Started), 1H, HT, 2H, ET, P, BT, SUSP, INT, FT, AET, PEN, AWD, WO
            live_statuses = ['1H', '2H', 'HT', 'ET', 'P', 'BT', 'SUSP', 'INT']
            
            fixtures = FixtureData.objects.filter(
                status_short__in=live_statuses
            ).order_by('date')[:limit]
            
            return fixtures
        except Exception as e:
            logger.error(f"Error obteniendo partidos en vivo: {e}")
            return []
    
    def get_recent_results(self, days=3, limit=5, league_id=None):
        """
        Obtener resultados recientes de partidos.
        
        Args:
            days: Número de días hacia atrás para buscar
            limit: Límite de resultados
            league_id: ID de la liga (opcional para filtrar)
            
        Returns:
            Lista de resultados recientes
        """
        try:
            now = timezone.now()
            past_date = now - timedelta(days=days)
            
            # Partidos finalizados tienen status_short FT, AET, PEN, AWD, WO
            finished_statuses = ['FT', 'AET', 'PEN', 'AWD', 'WO']
            
            query = Q(date__gte=past_date, date__lte=now, status_short__in=finished_statuses)
            
            if league_id:
                query &= Q(league_id=league_id)
                
            fixtures = FixtureData.objects.filter(query).order_by('-date')[:limit]
            return fixtures
        except Exception as e:
            logger.error(f"Error obteniendo resultados recientes: {e}")
            return []
    
    def format_fixtures_message(self, fixtures):
        """
        Formatear una lista de partidos como un mensaje de texto.
        
        Args:
            fixtures: Lista de objetos FixtureData
            
        Returns:
            Mensaje formateado con los partidos
        """
        if not fixtures:
            return "No hay partidos programados próximamente."
        
        message = "⚽ *PRÓXIMOS PARTIDOS* ⚽\n\n"
        
        for fixture in fixtures:
            # Formatear fecha en formato legible
            match_date = fixture.date.strftime("%d/%m/%Y %H:%M")
            
            # Crear línea de partido
            match_line = (
                f"🏆 *{fixture.league_name}* ({fixture.league_country})\n"
                f"⌚ {match_date}\n"
                f"{fixture.home_team_name} 🆚 {fixture.away_team_name}\n"
                f"🏟️ {fixture.venue_name or 'No disponible'}, {fixture.venue_city or 'No disponible'}\n"
                "───────────────────\n"
            )
            
            message += match_line
        
        message += "\nDatos proporcionados por Deep90"
        return message
    
    def format_results_message(self, fixtures):
        """
        Formatear una lista de resultados como un mensaje de texto.
        
        Args:
            fixtures: Lista de objetos FixtureData
            
        Returns:
            Mensaje formateado con los resultados
        """
        if not fixtures:
            return "No hay resultados recientes disponibles."
        
        message = "⚽ *RESULTADOS RECIENTES* ⚽\n\n"
        
        for fixture in fixtures:
            # Determinar resultado
            score = f"{fixture.home_goals or 0} - {fixture.away_goals or 0}"
            
            # Determinar estado (finalizado, suspendido, etc.)
            status = fixture.status_long

            # Formatear fecha en formato legible
            match_date = fixture.date.strftime("%d/%m/%Y")
            
            # Crear línea de resultado
            result_line = (
                f"🏆 *{fixture.league_name}* ({fixture.league_country})\n"
                f"📅 {match_date} | {status}\n"
                f"*{fixture.home_team_name}* {score} *{fixture.away_team_name}*\n"
                "───────────────────\n"
            )
            
            message += result_line
        
        message += "\nDatos proporcionados por Deep90"
        return message
    
    def format_live_matches_message(self, fixtures):
        """
        Formatea una lista de partidos en vivo como un mensaje de texto profesional,
        agrupando los partidos por país de la liga.

        Args:
            fixtures: Lista de objetos FixtureData

        Returns:
            Mensaje formateado con los partidos en vivo
        """
        if not fixtures:
            return "Actualmente no hay partidos en vivo."

        # Agrupar partidos por país de la liga
        leagues_by_country = defaultdict(list)
        for fixture in fixtures:
            leagues_by_country[fixture.league_country].append(fixture)

        message = "⚽ *Partidos en Vivo* ⚽\n\n"
        for country, country_fixtures in leagues_by_country.items():
            message += f"🌍 *{country}*\n\n"
            for fixture in country_fixtures:
                score = f"{fixture.home_goals or 0} - {fixture.away_goals or 0}"
                elapsed = f"{fixture.elapsed}'" if fixture.elapsed is not None else fixture.status_short
                match_line = (
                    f"🆔 {fixture.fixture_id}\n"
                    f"🏆 {fixture.league_name}\n"                    
                    f"⌚ {elapsed} | *{fixture.home_team_name}* {score} *{fixture.away_team_name}*\n"
                    "──────────────\n"
                )
                message += match_line
            message += "\n"

        message += "Información actualizada por Deep90."
        return message

