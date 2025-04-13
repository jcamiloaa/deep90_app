from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from .models import ScheduledTask, APIEndpoint, APIParameter


class GroupedModelChoiceField(forms.ModelChoiceField):
    """ModelChoiceField que soporta agrupación de opciones."""
    
    def __init__(self, group_by_field, *args, **kwargs):
        self.group_by_field = group_by_field
        super().__init__(*args, **kwargs)
    
    def _get_choices(self):
        """Obtiene opciones agrupadas para el campo."""
        if hasattr(self, '_choices'):
            return self._choices
        return GroupedModelChoiceIterator(self)
        
    # Sobreescribimos la propiedad choices sin usar _set_choices
    choices = property(_get_choices, lambda self, value: setattr(self, '_choices', value))


class GroupedModelChoiceIterator:
    """Iterador para opciones agrupadas."""
    
    def __init__(self, field):
        self.field = field
        self.queryset = field.queryset
        self.group_by_field = field.group_by_field
    
    def __iter__(self):
        if self.queryset is None:
            yield ("", self.field.empty_label)
            return
            
        # Determinar grupos basados en prefijos de endpoint
        groups = {}
        for item in self.queryset:
            # Determinar el grupo basado en el prefijo del endpoint
            endpoint_path = getattr(item, self.group_by_field)
            
            # Identificar el componente principal del endpoint
            if '/' in endpoint_path:
                # Para endpoints tipo 'teams/statistics', el grupo es 'teams'
                # Caso especial para endpoints de cuotas pre-partido
                if endpoint_path.startswith('odds/') and endpoint_path not in ['odds/live', 'odds/live/bets']:
                    group_key = 'Odds-Prematch'
                else:
                    group_key = endpoint_path.split('/')[0].capitalize()
            else:
                # Para endpoints simples como 'teams', 'leagues', etc.
                if endpoint_path in ['teams', 'leagues', 'venues', 'injuries', 'predictions', 'coachs', 'players', 'fixtures', 'standings', 'countries', 'transfers', 'trophies', 'sidelined']:
                    group_key = endpoint_path.capitalize()
                elif endpoint_path == 'odds':
                    group_key = 'Odds-Prematch'  # Caso especial para endpoint principal de cuotas pre-partido
                else:
                    group_key = 'General'
                
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append((item.pk, self._get_choice_label(item)))
        
        # Ordenar los grupos y devolver las opciones agrupadas
        if self.field.empty_label is not None:
            yield ("", self.field.empty_label)
        
        for group_name in sorted(groups.keys()):
            group_items = groups[group_name]
            yield (group_name, group_items)
    
    def _get_choice_label(self, item):
        """Obtiene la etiqueta para una opción."""
        endpoint_path = getattr(item, "endpoint")
        if '/' in endpoint_path:
            # Para endpoints tipo 'teams/statistics', mostrar solo la parte final
            return f"{item.name} ({endpoint_path.split('/')[-1]})"
        return f"{item.name} ({endpoint_path})"


class DynamicEndpointForm(forms.Form):
    """Formulario base para endpoints con parámetros dinámicos."""
    
    def __init__(self, endpoint, *args, **kwargs):
        """
        Inicializa el formulario con campos dinámicos basados en los parámetros del endpoint.
        
        Args:
            endpoint: APIEndpoint para el que se generarán los campos
            *args: Argumentos posicionales
            **kwargs: Argumentos con nombre
        """
        super().__init__(*args, **kwargs)
        self.endpoint = endpoint
        
        # Añade campos dinámicamente según los parámetros del endpoint
        for param in endpoint.parameters.all():
            field_kwargs = {
                'label': f"{param.name} ({param.get_parameter_type_display()})",
                'required': param.required,
                'help_text': param.description
            }
            
            # Crea el tipo de campo apropiado según el tipo de parámetro
            if param.parameter_type == 'integer':
                self.fields[param.name] = forms.IntegerField(**field_kwargs)
            elif param.parameter_type == 'boolean':
                self.fields[param.name] = forms.BooleanField(**field_kwargs)
            else:  # string u otros tipos
                self.fields[param.name] = forms.CharField(**field_kwargs)


class TaskScheduleForm(forms.ModelForm):
    """Formulario para programar una tarea."""
    
    class Meta:
        model = ScheduledTask
        fields = ['name', 'endpoint', 'schedule_type', 'scheduled_time', 'periodic_interval']
        widgets = {
            'scheduled_time': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}, 
                format='%Y-%m-%dT%H:%M'
            ),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['scheduled_time'].required = False
        self.fields['periodic_interval'].required = False
        
        # Añade clases CSS para mejor estilo
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})
    
    def clean(self):
        cleaned_data = super().clean()
        schedule_type = cleaned_data.get('schedule_type')
        scheduled_time = cleaned_data.get('scheduled_time')
        periodic_interval = cleaned_data.get('periodic_interval')
        
        # Valida que se proporcionen los campos necesarios según el tipo de programación
        if schedule_type == 'scheduled' and not scheduled_time:
            self.add_error(
                'scheduled_time', 
                _('Debe especificar una fecha y hora para tareas programadas.')
            )
        elif schedule_type == 'periodic' and not periodic_interval:
            self.add_error(
                'periodic_interval', 
                _('Debe especificar un intervalo para tareas periódicas.')
            )
        
        # Valida que la fecha programada sea futura
        if scheduled_time and scheduled_time <= timezone.now():
            self.add_error(
                'scheduled_time', 
                _('La fecha programada debe ser futura.')
            )
        
        return cleaned_data


class EndpointSelectionForm(forms.Form):
    """Formulario para seleccionar un endpoint."""
    endpoint = GroupedModelChoiceField(
        queryset=APIEndpoint.objects.all().order_by('endpoint'),
        group_by_field='endpoint',
        label=_("Seleccione un endpoint"),
        empty_label=_("Seleccione..."),
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class ParametersForm(forms.Form):
    """Formulario para introducir parámetros de un endpoint."""
    
    def __init__(self, endpoint_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if endpoint_id:
            endpoint = APIEndpoint.objects.get(id=endpoint_id)
            parameters = APIParameter.objects.filter(endpoint=endpoint)
            
            for param in parameters:
                field_type = forms.CharField
                field_kwargs = {
                    'label': f"{param.name}",
                    'required': param.required,
                    'help_text': param.description,
                    'widget': forms.TextInput(attrs={'class': 'form-control'})
                }
                
                if param.parameter_type == 'integer':
                    field_type = forms.IntegerField
                elif param.parameter_type == 'boolean':
                    field_type = forms.BooleanField
                    field_kwargs['widget'] = forms.CheckboxInput()
                
                self.fields[param.name] = field_type(**field_kwargs)