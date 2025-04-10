from django.contrib import admin
from .models import APIEndpoint, APIParameter, ScheduledTask, APIResult


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