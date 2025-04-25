from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.views.generic import ListView, DetailView, TemplateView, UpdateView
from django.views.generic.edit import FormView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.http import JsonResponse, HttpResponseRedirect
from django.utils import timezone
from django.db import transaction
from django.db.models import Count
from django_celery_beat.models import PeriodicTask
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST, require_GET
import json
import os
from django.conf import settings
from deep90_app.apps.whatsapp.sports_service import consultar_partido_en_vivo

from .models import (
    ScheduledTask, APIEndpoint, APIResult, 
    LiveFixtureTask, LiveOddsTask, 
    LiveFixtureData, LiveOddsData
)
from .forms import TaskScheduleForm, EndpointSelectionForm, ParametersForm
from .tasks import execute_api_request
from .live_tasks import toggle_task_status, restart_task, update_live_fixtures, update_live_odds


class AdminRequiredMixin(UserPassesTestMixin):
    """Mixin para requerir que el usuario sea administrador."""
    
    def test_func(self):
        return self.request.user.is_staff


class DashboardView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    """Vista dashboard para la administración de tareas API."""
    template_name = 'sports_data/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener estadísticas para el dashboard
        context['pending_tasks'] = ScheduledTask.objects.filter(status='pending').count()
        context['recent_tasks'] = ScheduledTask.objects.all().order_by('-created_at')[:5]
        context['failed_tasks'] = ScheduledTask.objects.filter(status='failed').count()
        context['endpoints_count'] = APIEndpoint.objects.count()
        
        return context


class TaskListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """Lista todas las tareas programadas."""
    model = ScheduledTask
    template_name = 'sports_data/task_list.html'
    context_object_name = 'tasks'
    paginate_by = 15
    
    def get_paginate_by(self, queryset):
        """Permite personalizar la cantidad de elementos por página."""
        per_page = self.request.GET.get('per_page')
        if per_page and per_page.isdigit() and int(per_page) > 0:
            return int(per_page)
        return self.paginate_by
    
    def get_queryset(self):
        queryset = ScheduledTask.objects.all()
        
        # Filtrar por estado
        status = self.request.GET.get('status')
        if status and status != 'all':
            queryset = queryset.filter(status=status)
            
        # Filtrar por tipo de programación
        schedule_type = self.request.GET.get('schedule_type')
        if schedule_type and schedule_type != 'all':
            queryset = queryset.filter(schedule_type=schedule_type)
            
        # Buscar por nombre o ID de tarea
        search_query = self.request.GET.get('search', '')
        if search_query:
            # Intentar convertir la búsqueda a un número para buscar por ID
            try:
                task_id = int(search_query)
                id_queryset = queryset.filter(id=task_id)
                if id_queryset.exists():
                    return id_queryset
            except ValueError:
                pass
            # Buscar por nombre (case insensitive)
            queryset = queryset.filter(name__icontains=search_query)
            
        # Ordenación
        sort_by = self.request.GET.get('sort_by', '-created_at')
        valid_sort_fields = ['name', '-name', 'created_at', '-created_at', 'status', '-status']
        if sort_by not in valid_sort_fields:
            sort_by = '-created_at'
        
        return queryset.order_by(sort_by)
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Añadir los parámetros de filtrado al contexto
        context['current_status'] = self.request.GET.get('status', 'all')
        context['current_schedule_type'] = self.request.GET.get('schedule_type', 'all')
        context['search_query'] = self.request.GET.get('search', '')
        context['current_sort_by'] = self.request.GET.get('sort_by', '-created_at')
        context['paginate_by'] = self.get_paginate_by(None)
        
        # Añadir contadores para la barra de filtros
        context['total_tasks'] = ScheduledTask.objects.count()
        context['pending_tasks'] = ScheduledTask.objects.filter(status='pending').count()
        context['running_tasks'] = ScheduledTask.objects.filter(status='running').count()
        context['success_tasks'] = ScheduledTask.objects.filter(status='success').count()
        context['failed_tasks'] = ScheduledTask.objects.filter(status='failed').count()
        context['cancelled_tasks'] = ScheduledTask.objects.filter(status='cancelled').count()
        
        return context


class TaskDetailView(LoginRequiredMixin, AdminRequiredMixin, DetailView):
    """Detalle de una tarea programada."""
    model = ScheduledTask
    template_name = 'sports_data/task_detail.html'
    context_object_name = 'task'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Añadir resultados de la tarea
        context['results'] = self.object.results.all().order_by('-executed_at')
        
        # Verificar si hay un resultado exitoso para mostrar
        latest_success = self.object.results.filter(success=True).order_by('-executed_at').first()
        context['latest_success'] = latest_success
        
        return context


class CreateTaskWizardView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    """Vista wizard para crear una nueva tarea programada."""
    template_name = 'sports_data/create_task_wizard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Paso 1: Selección de endpoint
        step = self.kwargs.get('step', 1)
        context['step'] = step
        
        if step == 1:
            context['form'] = EndpointSelectionForm()
        elif step == 2:
            endpoint_id = self.request.GET.get('endpoint')
            if endpoint_id:
                endpoint = get_object_or_404(APIEndpoint, pk=endpoint_id)
                context['endpoint'] = endpoint
                if endpoint.has_parameters:
                    context['form'] = ParametersForm(endpoint_id=endpoint_id)
        elif step == 3:
            endpoint_id = self.request.GET.get('endpoint')
            context['endpoint'] = get_object_or_404(APIEndpoint, pk=endpoint_id)
            context['form'] = TaskScheduleForm(initial={'endpoint': endpoint_id})
            
            # Recuperar parámetros de la sesión
            if 'parameters' in self.request.session:
                context['parameters'] = self.request.session['parameters']
        
        return context
    
    def post(self, request, *args, **kwargs):
        step = self.kwargs.get('step', 1)
        
        if step == 1:
            form = EndpointSelectionForm(request.POST)
            if form.is_valid():
                endpoint = form.cleaned_data['endpoint']
                return redirect(f"{reverse('sports_data:create-task-wizard', kwargs={'step': 2})}?endpoint={endpoint.id}")
            else:
                return render(request, self.template_name, {'form': form, 'step': step})
        
        elif step == 2:
            endpoint_id = request.GET.get('endpoint')
            endpoint = get_object_or_404(APIEndpoint, pk=endpoint_id)
            
            if endpoint.has_parameters:
                form = ParametersForm(endpoint_id=endpoint_id, data=request.POST)
                if form.is_valid():
                    # Guardar parámetros en sesión
                    request.session['parameters'] = form.cleaned_data
                    return redirect(f"{reverse('sports_data:create-task-wizard', kwargs={'step': 3})}?endpoint={endpoint_id}")
                else:
                    return render(request, self.template_name, {
                        'form': form, 
                        'step': step, 
                        'endpoint': endpoint
                    })
            else:
                # Si no tiene parámetros, limpiar la sesión y continuar
                if 'parameters' in request.session:
                    del request.session['parameters']
                return redirect(f"{reverse('sports_data:create-task-wizard', kwargs={'step': 3})}?endpoint={endpoint_id}")
        
        elif step == 3:
            endpoint_id = request.GET.get('endpoint')
            form = TaskScheduleForm(request.POST)
            
            if form.is_valid():
                # Crear la tarea con los datos recopilados
                with transaction.atomic():
                    task = form.save(commit=False)
                    task.created_by = request.user
                    
                    # Recuperar parámetros de sesión
                    if 'parameters' in request.session:
                        task.parameters = request.session['parameters']
                        del request.session['parameters']
                    
                    task.save()
                    
                    # Si la tarea es inmediata, ejecutarla ahora
                    if task.schedule_type == 'immediate':
                        execute_api_request.delay(task_id=task.id)
                    elif task.schedule_type == 'scheduled':
                        # Programar la tarea para ejecutarse en el futuro
                        execute_api_request.apply_async(
                            kwargs={'task_id': task.id},
                            eta=task.scheduled_time
                        )
                    # Las tareas periódicas se manejan con el task schedule_periodic_tasks
                
                messages.success(request, 'Tarea creada con éxito.')
                return redirect('sports_data:task-detail', pk=task.id)
            else:
                endpoint = get_object_or_404(APIEndpoint, pk=endpoint_id)
                parameters = request.session.get('parameters', {})
                return render(request, self.template_name, {
                    'form': form, 
                    'step': step, 
                    'endpoint': endpoint,
                    'parameters': parameters
                })
        
        return redirect('sports_data:create-task-wizard', step=1)


class ExecuteTaskView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    """Vista para ejecutar una tarea manualmente."""
    
    def post(self, request, pk):
        task = get_object_or_404(ScheduledTask, pk=pk)
        
        # Ejecutar la tarea de forma asincrónica
        result = execute_api_request.delay(task_id=task.id)
        messages.success(request, f'Tarea {task.name} iniciada. ID: {result.id}')
        
        return redirect('sports_data:task-detail', pk=task.id)


class ResultDetailView(LoginRequiredMixin, AdminRequiredMixin, DetailView):
    """Detalle de un resultado de API."""
    model = APIResult
    template_name = 'sports_data/result_detail.html'
    context_object_name = 'result'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['task'] = self.object.task
        
        # Formatear los datos JSON para mostrarlos
        if self.object.response_data:
            import json
            context['formatted_data'] = json.dumps(self.object.response_data, indent=2)
        
        return context


class EditTaskView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    """Vista para editar tareas."""
    model = ScheduledTask
    form_class = TaskScheduleForm
    template_name = 'sports_data/edit_task.html'
    
    def get_queryset(self):
        # Permitir editar tareas pendientes, completadas o fallidas
        # No permitimos editar tareas en ejecución
        return ScheduledTask.objects.exclude(status='running')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        task = self.get_object()
        
        # Crear el formulario para editar los parámetros
        if task.endpoint.has_parameters:
            # Si hay datos POST, usamos esos datos para inicializar el formulario
            if self.request.method == 'POST':
                context['param_form'] = ParametersForm(
                    endpoint_id=task.endpoint.id, 
                    data=self.request.POST
                )
            else:
                # Si no hay POST, inicializamos con los parámetros actuales
                context['param_form'] = ParametersForm(
                    endpoint_id=task.endpoint.id, 
                    initial=task.parameters
                )
        
        return context
    
    def form_valid(self, form):
        task = self.get_object()
        
        with transaction.atomic():
            # Guardar la tarea con los nuevos datos
            updated_task = form.save(commit=False)
            
            # Si la tarea ya fue ejecutada (success o failed), cambiar estado a pending
            if task.status in ['success', 'failed']:
                updated_task.status = 'pending'
            
            # Procesar los parámetros del formulario si el endpoint tiene parámetros
            if task.endpoint.has_parameters:
                param_form = ParametersForm(
                    endpoint_id=task.endpoint.id,
                    data=self.request.POST
                )
                
                if param_form.is_valid():
                    # Actualizar los parámetros con los valores del formulario
                    updated_task.parameters = param_form.cleaned_data
                else:
                    # Si el formulario de parámetros no es válido, mostrar errores
                    return self.form_invalid(form)
            
            # Si la tarea era periódica y hay una tarea de Celery Beat asociada, actualizarla o eliminarla
            if task.celery_task_id:
                try:
                    periodic_task = PeriodicTask.objects.get(id=task.celery_task_id)
                    
                    if updated_task.schedule_type != 'periodic':
                        # Si la tarea deja de ser periódica, eliminar la tarea de Celery Beat
                        periodic_task.delete()
                        updated_task.celery_task_id = None
                    else:
                        # Si sigue siendo periódica pero cambian intervalos, actualizar
                        from django_celery_beat.models import IntervalSchedule
                        
                        schedule, created = IntervalSchedule.objects.get_or_create(
                            every=updated_task.periodic_interval,
                            period=IntervalSchedule.MINUTES,
                        )
                        periodic_task.interval = schedule
                        periodic_task.save()
                except PeriodicTask.DoesNotExist:
                    pass
            
            # Si la tarea es programada y ha cambiado la hora, actualizar la tarea programada
            if updated_task.schedule_type == 'scheduled' and task.scheduled_time != updated_task.scheduled_time:
                # Programar la tarea para ejecutarse en el futuro
                execute_api_request.apply_async(
                    kwargs={'task_id': task.id},
                    eta=updated_task.scheduled_time
                )
                
            updated_task.save()
            
        messages.success(self.request, f'Tarea "{updated_task.name}" actualizada correctamente y puesta en espera para la próxima ejecución.')
        return HttpResponseRedirect(reverse('sports_data:task-detail', kwargs={'pk': task.id}))
        
    def form_invalid(self, form):
        # Este método se llama cuando hay errores de validación en el formulario principal
        # o en el formulario de parámetros
        return self.render_to_response(self.get_context_data(form=form))


class CancelTaskView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    """Vista para cancelar una tarea pendiente."""
    
    def post(self, request, pk):
        task = get_object_or_404(ScheduledTask, pk=pk)
        
        # Solo permitir cancelar tareas pendientes
        if task.status != 'pending':
            messages.error(request, f'No se puede cancelar la tarea "{task.name}" porque ya está en ejecución o ha finalizado.')
            return redirect('sports_data:task-detail', pk=task.id)
        
        with transaction.atomic():
            # Si hay una tarea periódica asociada, eliminarla
            if task.celery_task_id:
                try:
                    periodic_task = PeriodicTask.objects.get(id=task.celery_task_id)
                    periodic_task.delete()
                except PeriodicTask.DoesNotExist:
                    pass
            
            # Marcar la tarea como cancelada usando el nuevo estado 'cancelled'
            task.status = 'cancelled'
            task.save()
            
            # Crear un registro de resultado que indique que fue cancelada manualmente
            APIResult.objects.create(
                task=task,
                executed_at=timezone.now(),
                response_code=0,
                response_data=None,
                execution_time=0,
                success=False,
                error_message="Tarea cancelada manualmente por el usuario."
            )
        
        messages.success(request, f'Tarea "{task.name}" cancelada correctamente.')
        return redirect('sports_data:task-detail', pk=task.id)


def live_dashboard(request):
    """
    Vista para el dashboard de seguimiento de datos en vivo de fútbol
    """
    # Obtener la hora actual para comparar con next_run
    now = timezone.now()
    
    # Obtener tareas de partidos en vivo
    fixture_tasks = LiveFixtureTask.objects.all().order_by('-is_enabled', 'name')
    
    # Obtener tareas de cuotas en vivo
    odds_tasks = LiveOddsTask.objects.all().order_by('-is_enabled', 'name')
    
    # Obtener partidos en vivo actuales
    live_fixtures = LiveFixtureData.objects.all().order_by(
        'league_name', 'home_team_name'
    ).select_related('task')
    
    # Obtener datos para las gráficas
    fixture_status_data = get_fixture_status_chart_data()
    league_data = get_league_chart_data()
    odds_stats = get_odds_chart_data()
    
    # Obtener ligas únicas para el filtro
    leagues = get_unique_leagues(live_fixtures)
    
    # Enriquecer datos de partidos con información de cuotas si está disponible
    live_fixtures = enrich_fixtures_with_odds(live_fixtures)
    
    context = {
        'now': now,  # Pasar la hora actual a la plantilla
        'fixture_tasks': fixture_tasks,
        'odds_tasks': odds_tasks,
        'live_fixtures': live_fixtures,
        'fixture_status_data': fixture_status_data,
        'league_data': league_data,
        'leagues': leagues,
        'odds_active': odds_stats['active'],
        'odds_blocked': odds_stats['blocked'],
        'odds_stopped': odds_stats['stopped'],
        'odds_finished': odds_stats['finished'],
    }
    
    return render(request, 'sports_data/live_dashboard.html', context)


def get_fixture_status_chart_data():
    """
    Obtiene datos formateados para el gráfico de estado de partidos
    """
    status_counts = LiveFixtureData.objects.values('status_short').annotate(count=Count('status_short'))
    
    # Mapeo de códigos a etiquetas más descriptivas
    status_labels = {
        '1H': 'Primera parte',
        '2H': 'Segunda parte',
        'HT': 'Descanso',
        'FT': 'Finalizado',
        'ET': 'Prórroga',
        'BT': 'Pausa',
        'P': 'Penaltis',
        'NS': 'No iniciado',
        'AET': 'Fin Prórroga',
        'PEN': 'Fin Penaltis',
        'SUSP': 'Suspendido',
        'INT': 'Interrumpido',
        'PST': 'Pospuesto',
        'CANC': 'Cancelado',
        'ABD': 'Abandonado',
        'AWD': 'Adjudicado',
        'WO': 'Walkover',
        'LIVE': 'En vivo',
        'TBD': 'A determinar',
    }
    
    chart_data = []
    for item in status_counts:
        status_code = item['status_short']
        label = status_labels.get(status_code, status_code)
        chart_data.append((label, item['count']))
    
    # Ordenar por cantidad descendente
    chart_data.sort(key=lambda x: x[1], reverse=True)
    
    return chart_data


def get_league_chart_data():
    """
    Obtiene datos formateados para el gráfico de partidos por liga
    """
    league_counts = LiveFixtureData.objects.values('league_name', 'league_id').annotate(
        count=Count('league_id')
    ).order_by('-count')
    
    # Limitar a las 8 ligas principales
    return list(league_counts[:8])


def get_odds_chart_data():
    """
    Obtiene estadísticas sobre el estado de las cuotas
    """
    odds_data = LiveOddsData.objects.all()
    
    stats = {
        'active': odds_data.filter(is_blocked=False, is_stopped=False, is_finished=False).count(),
        'blocked': odds_data.filter(is_blocked=True).count(),
        'stopped': odds_data.filter(is_blocked=False, is_stopped=True, is_finished=False).count(),
        'finished': odds_data.filter(is_finished=True).count(),
    }
    
    return stats


def get_unique_leagues(fixtures):
    """
    Obtiene lista de ligas únicas para el filtro del dashboard
    """
    leagues = {}
    for fixture in fixtures:
        if fixture.league_id not in leagues:
            leagues[fixture.league_id] = {
                'id': fixture.league_id,
                'name': fixture.league_name,
                'country': getattr(fixture, 'league_country', '')
            }
    
    # Convertir el diccionario a una lista ordenada por nombre
    sorted_leagues = sorted(leagues.values(), key=lambda x: x['name'])
    
    return sorted_leagues


def enrich_fixtures_with_odds(fixtures):
    """
    Enriquece los datos de partidos con información de cuotas
    """
    # Obtener IDs de todos los partidos
    fixture_ids = [fixture.fixture_id for fixture in fixtures]
    
    # Obtener todas las cuotas relacionadas en una sola consulta
    odds_data = LiveOddsData.objects.filter(fixture_id__in=fixture_ids)
    
    # Crear un diccionario para acceso rápido
    odds_dict = {odds.fixture_id: odds for odds in odds_data}
    
    # Crear una copia profunda de los fixtures para manipular
    enriched_fixtures = []
    
    for fixture in fixtures:
        # Crear una copia del fixture como diccionario
        fixture_dict = {
            'fixture_id': fixture.fixture_id,
            'league_id': fixture.league_id,
            'league_name': fixture.league_name,
            'league_country': getattr(fixture, 'league_country', ''),
            'league_logo': fixture.league_logo,  # Aseguramos que el logo de la liga se incluya
            'home_team_name': fixture.home_team_name,
            'home_team_logo': fixture.home_team_logo,
            'home_goals': fixture.home_goals,
            'away_team_name': fixture.away_team_name,
            'away_team_logo': fixture.away_team_logo,
            'away_goals': fixture.away_goals,
            'status_short': fixture.status_short,
            'status_long': fixture.status_long,
            'elapsed': fixture.elapsed,
            'elapsed_seconds': getattr(fixture, 'elapsed_seconds', None),
            'venue_name': getattr(fixture, 'venue_name', ''),
            'venue_city': getattr(fixture, 'venue_city', ''),
            'date': getattr(fixture, 'date', None),
            'odds': None,  # Placeholder para las cuotas
        }
        
        # Añadir información de cuotas si está disponible
        if fixture.fixture_id in odds_dict:
            live_odds = odds_dict[fixture.fixture_id]
            odds_values = {}
            
            # Buscar categoría "Match Winner" (Ganador del partido)
            try:
                match_winner_category = live_odds.odds_categories.filter(name__icontains="Match Winner").first()
                
                if match_winner_category:
                    # Obtener valores para esta categoría
                    for value in match_winner_category.values.all():
                        if value.value == 'Home':
                            odds_values['home'] = float(value.odd)
                        elif value.value == 'Draw':
                            odds_values['draw'] = float(value.odd)
                        elif value.value == 'Away':
                            odds_values['away'] = float(value.odd)
                
                # Si no encontramos valores específicos, intentar con Double Chance
                if not odds_values:
                    double_chance = live_odds.odds_categories.filter(name__icontains="Double Chance").first()
                    if double_chance:
                        # Para doble oportunidad, los valores son diferentes
                        dc_values = {}
                        for value in double_chance.values.all():
                            dc_values[value.value] = float(value.odd)
                        
                        # Añadir estos valores al diccionario
                        fixture_dict['double_chance'] = dc_values
                    
                # Añadir "Over/Under" si existe
                over_under = live_odds.odds_categories.filter(name__icontains="Over/Under").first()
                if over_under:
                    ou_values = {}
                    for value in over_under.values.all():
                        handicap = value.handicap or "2.5"  # Valor por defecto
                        key = f"{value.value}_{handicap}"
                        ou_values[key] = float(value.odd)
                    
                    # Añadir al diccionario
                    fixture_dict['over_under'] = ou_values
                
                if odds_values:
                    fixture_dict['odds'] = odds_values
                
            except Exception as e:
                # Si hay error al procesar las cuotas, simplemente no las incluimos
                pass
                
        enriched_fixtures.append(fixture_dict)
    
    return enriched_fixtures


@require_POST
@csrf_exempt
def toggle_live_task(request, task_type, task_id):
    """
    API para activar/desactivar una tarea en vivo
    """
    # Verificar que el usuario tiene permisos
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'message': 'Permisos insuficientes'}, status=403)
    
    from .live_tasks import toggle_task_status
    result = toggle_task_status(task_type, task_id)
    
    return JsonResponse(result)


@require_POST
@csrf_exempt
def restart_live_task(request, task_type, task_id):
    """
    API para reiniciar una tarea fallida
    """
    # Verificar que el usuario tiene permisos
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'message': 'Permisos insuficientes'}, status=403)
    
    from .live_tasks import restart_task
    result = restart_task(task_type, task_id)
    
    return JsonResponse(result)


@require_POST
@csrf_exempt
def reset_stalled_task(request, task_type, task_id):
    """
    API para reiniciar una tarea con next_run en el pasado
    """
    # Verificar que el usuario tiene permisos
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'message': 'Permisos insuficientes'}, status=403)
    
    from .live_tasks import reset_stalled_tasks
    result = reset_stalled_tasks(task_type=task_type, task_id=task_id)
    
    return JsonResponse(result)


@require_POST
@csrf_exempt
def reset_all_stalled_tasks(request):
    """
    API para reiniciar todas las tareas con next_run en el pasado
    """
    # Verificar que el usuario tiene permisos
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'message': 'Permisos insuficientes'}, status=403)
    
    from .live_tasks import reset_stalled_tasks
    result = reset_stalled_tasks()
    
    return JsonResponse(result)


@require_GET
def fixture_odds_detail(request, fixture_id):
    """
    Vista para mostrar todas las cuotas disponibles de un partido específico.
    """
    # Obtener los datos del partido
    try:
        fixture = LiveFixtureData.objects.filter(fixture_id=fixture_id).first()
        if not fixture:
            messages.error(request, f"No se encontró el partido con ID {fixture_id}")
            return redirect('sports_data:live-dashboard')
        
        # Obtener las cuotas para este partido
        odds_data = LiveOddsData.objects.filter(fixture_id=fixture_id).first()
        
        # Si no hay cuotas disponibles
        if not odds_data:
            context = {
                'fixture': fixture,
                'has_odds': False
            }
            return render(request, 'sports_data/fixture_odds_detail.html', context)
        
        # Obtener todas las categorías de cuotas con sus respectivos valores
        odds_categories = odds_data.odds_categories.all().prefetch_related('values')
        
        # Organizar las categorías por tipos comunes
        organized_categories = {
            'main': [],       # Categorías principales como Match Winner, Double Chance
            'goals': [],      # Categorías de goles como Over/Under, Exact Score
            'halftime': [],   # Categorías de primer tiempo
            'corners': [],    # Esquinas
            'cards': [],      # Tarjetas
            'other': []       # Otras categorías
        }
        
        # Clasificar cada categoría
        for category in odds_categories:
            if any(term in category.name.lower() for term in ['winner', 'win', '1x2', 'chance']):
                organized_categories['main'].append(category)
            elif any(term in category.name.lower() for term in ['goal', 'score', 'over', 'under', 'btts']):
                organized_categories['goals'].append(category)
            elif any(term in category.name.lower() for term in ['half', 'halftime', '1st']):
                organized_categories['halftime'].append(category)
            elif 'corner' in category.name.lower():
                organized_categories['corners'].append(category)
            elif any(term in category.name.lower() for term in ['card', 'booking', 'yellow', 'red']):
                organized_categories['cards'].append(category)
            else:
                organized_categories['other'].append(category)
        
        context = {
            'fixture': fixture,
            'odds_data': odds_data,
            'categories': organized_categories,
            'has_odds': True
        }
        
        return render(request, 'sports_data/fixture_odds_detail.html', context)
    
    except Exception as e:
        messages.error(request, f"Error al obtener las cuotas: {str(e)}")
        return redirect('sports_data:live-dashboard')


@staff_member_required
@require_POST
@csrf_exempt
def run_update_live_fixtures(request):
    """Ejecuta manualmente la tarea de actualización de partidos en vivo."""
    from .models import LiveFixtureTask
    task = LiveFixtureTask.objects.filter(is_enabled=True).order_by('id').first()
    if not task:
        return JsonResponse({'success': False, 'message': 'No hay tarea de partidos en vivo habilitada.'})
    result = update_live_fixtures.apply(args=(task.id,)).get()
    return JsonResponse({'success': result.get('success', False), 'message': result.get('message', 'Tarea ejecutada.'), 'details': result})


@staff_member_required
@require_POST
@csrf_exempt
def run_update_live_odds(request):
    """Ejecuta manualmente la tarea de actualización de cuotas en vivo."""
    from .models import LiveOddsTask
    task = LiveOddsTask.objects.filter(is_enabled=True).order_by('id').first()
    if not task:
        return JsonResponse({'success': False, 'message': 'No hay tarea de cuotas en vivo habilitada.'})
    result = update_live_odds.apply(args=(task.id,)).get()
    return JsonResponse({'success': result.get('success', False), 'message': result.get('message', 'Tarea ejecutada.'), 'details': result})


def fixture_widget(request, fixture_id):
    """
    Vista para mostrar solo el widget de API-Football para un partido.
    """
    api_football_key = os.environ.get('API_FOOTBALL_KEY') or getattr(settings, 'API_FOOTBALL_KEY', None)
    context = {
        'fixture_id': fixture_id,
        'api_football_key': api_football_key,
    }
    return render(request, 'sports_data/fixture_widget.html', context)


@require_GET
def api_live_fixture_detail(request, fixture_id):
    """
    API: Devuelve el JSON estructurado de un partido en vivo y sus odds.
    """
    json_result = consultar_partido_en_vivo(fixture_id)
    return JsonResponse(json.loads(json_result), safe=False)
