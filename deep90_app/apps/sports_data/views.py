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
from django_celery_beat.models import PeriodicTask

from .models import ScheduledTask, APIEndpoint, APIResult
from .forms import TaskScheduleForm, EndpointSelectionForm, ParametersForm
from .tasks import execute_api_request


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
    """Vista para editar tareas que aún no se hayan ejecutado."""
    model = ScheduledTask
    form_class = TaskScheduleForm
    template_name = 'sports_data/edit_task.html'
    
    def get_queryset(self):
        # Solo permitir editar tareas pendientes o programadas que no se hayan ejecutado
        return ScheduledTask.objects.filter(status='pending')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        task = self.get_object()
        
        # Mostrar los parámetros de la tarea si existen
        if task.parameters:
            context['parameters'] = task.parameters
        
        return context
    
    def form_valid(self, form):
        task = self.get_object()
        
        with transaction.atomic():
            # Guardar la tarea con los nuevos datos
            updated_task = form.save(commit=False)
            
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
            
        messages.success(self.request, f'Tarea "{updated_task.name}" actualizada correctamente.')
        return HttpResponseRedirect(reverse('sports_data:task-detail', kwargs={'pk': task.id}))


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
