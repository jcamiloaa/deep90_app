from datetime import datetime
from django.utils.timezone import make_aware
from .models import APIResult, FixtureData, LeagueData, StandingData


class ResponseProcessor:
    """
    Servicio para procesar respuestas de la API y almacenar datos estructurados.
    """
    
    @staticmethod
    def process_result(result_id):
        """
        Procesa el resultado de una API y extrae datos estructurados si corresponde.
        
        Args:
            result_id: ID del resultado API a procesar
        """
        result = APIResult.objects.get(pk=result_id)
        
        # No procesar resultados fallidos
        if not result.success or not result.response_data:
            return
        
        # Determinar qué tipo de endpoint es y procesarlo adecuadamente
        endpoint_path = result.task.endpoint.endpoint.lower()
        
        if endpoint_path == 'fixtures' or endpoint_path.startswith('fixtures/'):
            ResponseProcessor._process_fixtures(result)
        elif endpoint_path == 'leagues' or endpoint_path.startswith('leagues/'):
            ResponseProcessor._process_leagues(result)
        elif endpoint_path == 'standings':
            ResponseProcessor._process_standings(result)
    
    @staticmethod
    def _process_fixtures(result):
        """
        Procesa los datos de respuesta del endpoint 'fixtures'.
        
        Args:
            result: Objeto APIResult con los datos a procesar
        """
        data = result.response_data
        
        # Verificar si es una respuesta válida
        if not data.get('response'):
            # Si no hay respuesta válida, eliminamos todos los datos existentes
            FixtureData.objects.all().delete()
            return
        
        # Eliminar todos los datos existentes antes de cargar los nuevos
        FixtureData.objects.all().delete()
        
        # Iterar a través de cada partido en la respuesta
        for fixture_data in data['response']:
            try:
                fixture = fixture_data.get('fixture', {})
                teams = fixture_data.get('teams', {})
                goals = fixture_data.get('goals', {})
                score = fixture_data.get('score', {})
                league = fixture_data.get('league', {})
                
                # Parsear la fecha a un objeto datetime con zona horaria
                date_str = fixture.get('date')
                try:
                    date = datetime.fromisoformat(date_str.replace('Z', '+00:00')) if date_str else None
                except (ValueError, AttributeError):
                    date = None
                
                # Crear registro en FixtureData
                FixtureData.objects.create(
                    result=result,
                    fixture_id=fixture.get('id', 0),
                    date=date,
                    timestamp=fixture.get('timestamp', 0),
                    timezone=fixture.get('timezone', 'UTC'),
                    status_long=fixture.get('status', {}).get('long', ''),
                    status_short=fixture.get('status', {}).get('short', ''),
                    elapsed=fixture.get('status', {}).get('elapsed'),
                    venue_id=fixture.get('venue', {}).get('id'),
                    venue_name=fixture.get('venue', {}).get('name'),
                    venue_city=fixture.get('venue', {}).get('city'),
                    
                    home_team_id=teams.get('home', {}).get('id', 0),
                    home_team_name=teams.get('home', {}).get('name', ''),
                    home_team_logo=teams.get('home', {}).get('logo'),
                    home_team_winner=teams.get('home', {}).get('winner'),
                    
                    away_team_id=teams.get('away', {}).get('id', 0),
                    away_team_name=teams.get('away', {}).get('name', ''),
                    away_team_logo=teams.get('away', {}).get('logo'),
                    away_team_winner=teams.get('away', {}).get('winner'),
                    
                    home_goals=goals.get('home'),
                    away_goals=goals.get('away'),
                    
                    home_halftime=score.get('halftime', {}).get('home'),
                    away_halftime=score.get('halftime', {}).get('away'),
                    home_fulltime=score.get('fulltime', {}).get('home'),
                    away_fulltime=score.get('fulltime', {}).get('away'),
                    home_extratime=score.get('extratime', {}).get('home'),
                    away_extratime=score.get('extratime', {}).get('away'),
                    home_penalty=score.get('penalty', {}).get('home'),
                    away_penalty=score.get('penalty', {}).get('away'),
                    
                    league_id=league.get('id', 0),
                    league_name=league.get('name', ''),
                    league_country=league.get('country', ''),
                    league_logo=league.get('logo'),
                    league_flag=league.get('flag'),
                    league_season=league.get('season', 0),
                    league_round=league.get('round', '')
                )
            except Exception as e:
                # Registrar error sin interrumpir el procesamiento del resto
                print(f"Error procesando fixture: {e}")

    @staticmethod
    def _process_leagues(result):
        """
        Procesa los datos de respuesta del endpoint 'leagues'.
        
        Args:
            result: Objeto APIResult con los datos a procesar
        """
        data = result.response_data
        
        # Verificar si es una respuesta válida
        if not data.get('response'):
            return
        
        # Eliminar todos los datos existentes antes de cargar los nuevos
        # Esto garantiza que no haya datos históricos, solo los más recientes
        LeagueData.objects.filter(result__task__endpoint=result.task.endpoint).delete()
        
        # Iterar a través de cada liga en la respuesta
        for league_data in data['response']:
            try:
                league = league_data.get('league', {})
                country = league_data.get('country', {})
                seasons = league_data.get('seasons', [])
                
                # Si hay temporadas, procesar cada una
                if seasons:
                    for season in seasons:
                        # Obtener información de cobertura
                        coverage = season.get('coverage', {})
                        fixtures_coverage = coverage.get('fixtures', {})
                        
                        LeagueData.objects.create(
                            result=result,
                            league_id=league.get('id', 0),
                            name=league.get('name', ''),
                            type=league.get('type', ''),
                            logo=league.get('logo'),
                            country=country.get('name', ''),
                            country_code=country.get('code'),
                            flag=country.get('flag'),
                            season=season.get('year'),
                            season_start=season.get('start'),
                            season_end=season.get('end'),
                            standings=coverage.get('standings', False),
                            is_current=season.get('current', False),
                            
                            # Campos de cobertura
                            coverage_fixtures=bool(fixtures_coverage),
                            coverage_fixtures_events=fixtures_coverage.get('events', False),
                            coverage_fixtures_lineups=fixtures_coverage.get('lineups', False),
                            coverage_fixtures_statistics_players=fixtures_coverage.get('statistics_players', False),
                            coverage_fixtures_statistics_fixtures=fixtures_coverage.get('statistics_fixtures', False),
                            coverage_players=coverage.get('players', False),
                            coverage_top_scorers=coverage.get('top_scorers', False),
                            coverage_top_assists=coverage.get('top_assists', False),
                            coverage_top_cards=coverage.get('top_cards', False),
                            coverage_injuries=coverage.get('injuries', False),
                            coverage_predictions=coverage.get('predictions', False),
                            coverage_odds=coverage.get('odds', False)
                        )
                else:
                    # Si no hay temporadas, crear un registro básico
                    LeagueData.objects.create(
                        result=result,
                        league_id=league.get('id', 0),
                        name=league.get('name', ''),
                        type=league.get('type', ''),
                        logo=league.get('logo'),
                        country=country.get('name', ''),
                        country_code=country.get('code'),
                        flag=country.get('flag')
                    )
            except Exception as e:
                print(f"Error procesando liga: {e}")

    @staticmethod
    def _process_standings(result):
        """
        Procesa los datos de respuesta del endpoint 'standings'.
        
        Args:
            result: Objeto APIResult con los datos a procesar
        """
        data = result.response_data
        
        # Verificar si es una respuesta válida
        if not data.get('response'):
            # Si no hay respuesta válida, eliminamos todos los datos existentes
            StandingData.objects.all().delete()
            return
        
        # Eliminar todos los datos existentes antes de cargar los nuevos
        StandingData.objects.all().delete()
        
        # Iterar a través de cada liga en la respuesta
        for league_standings in data['response']:
            try:
                league = league_standings.get('league', {})
                league_id = league.get('id', 0)
                league_name = league.get('name', '')
                season = league.get('season', 0)
                
                # Procesar todos los grupos de clasificación (puede haber múltiples en copas)
                for standings_group in league.get('standings', []):
                    for team_data in standings_group:
                        team = team_data.get('team', {})
                        goals = team_data.get('all', {}).get('goals', {})
                        
                        StandingData.objects.create(
                            result=result,
                            league_id=league_id,
                            league_name=league_name,
                            season=season,
                            team_id=team.get('id', 0),
                            team_name=team.get('name', ''),
                            team_logo=team.get('logo'),
                            rank=team_data.get('rank', 0),
                            group=team_data.get('group'),
                            form=team_data.get('form'),
                            played=team_data.get('all', {}).get('played', 0),
                            win=team_data.get('all', {}).get('win', 0),
                            draw=team_data.get('all', {}).get('draw', 0),
                            lose=team_data.get('all', {}).get('lose', 0),
                            goals_for=goals.get('for', 0),
                            goals_against=goals.get('against', 0),
                            goals_diff=team_data.get('goalsDiff', 0),
                            points=team_data.get('points', 0),
                            description=team_data.get('description')
                        )
            except Exception as e:
                print(f"Error procesando clasificación: {e}")