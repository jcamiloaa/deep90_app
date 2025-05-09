from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import WhatsAppUser, Conversation, Message, UserInput, UserPreference, AssistantConfig


@admin.register(WhatsAppUser)
class WhatsAppUserAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'profile_name', 'full_name', 'email', 'birth_date','country', 'city','status', 
                     'subscription_plan', 'created_at', 'last_activity']
    
    list_filter = ['status', 'subscription_plan', 'is_blacklisted', 'created_at']
    search_fields = ['phone_number', 'profile_name', 'full_name', 'email']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (_('Información básica'), {
            'fields': ('phone_number', 'profile_name', 'full_name', 'email', 'birth_date')
        }),
        (_('Ubicación'), {
            'fields': ('country', 'city')
        }),
        (_('Estado y suscripción'), {
            'fields': ('status', 'subscription_plan', 'subscription_expiry', 'is_blacklisted')
        }),
        (_('Fechas'), {
            'fields': ('created_at', 'updated_at', 'last_activity')
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'last_activity']
    
    actions = ['mark_as_registered', 'mark_as_suspended', 'mark_as_banned', 
               'set_subscription_free', 'set_subscription_premium', 'set_subscription_pro']
    
    def mark_as_registered(self, request, queryset):
        queryset.update(status='registered')
    mark_as_registered.short_description = _("Marcar como registrados")
    
    def mark_as_suspended(self, request, queryset):
        queryset.update(status='suspended')
    mark_as_suspended.short_description = _("Marcar como suspendidos")
    
    def mark_as_banned(self, request, queryset):
        queryset.update(status='banned', is_blacklisted=True)
    mark_as_banned.short_description = _("Marcar como bloqueados")
    
    def set_subscription_free(self, request, queryset):
        queryset.update(subscription_plan='free')
    set_subscription_free.short_description = _("Establecer suscripción gratuita")
    
    def set_subscription_premium(self, request, queryset):
        queryset.update(subscription_plan='premium')
    set_subscription_premium.short_description = _("Establecer suscripción premium")
    
    def set_subscription_pro(self, request, queryset):
        queryset.update(subscription_plan='pro')
    set_subscription_pro.short_description = _("Establecer suscripción profesional")


class MessageInline(admin.TabularInline):
    model = Message
    fields = ['created_at', 'is_from_user', 'message_type', 'content_preview']
    readonly_fields = ['created_at', 'is_from_user', 'message_type', 'content_preview']
    extra = 0
    max_num = 0
    can_delete = False
    ordering = ['-created_at']
    
    def content_preview(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_preview.short_description = _("Contenido")


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'conversation_type', 'is_active', 'thread_id', 'fixture_id', 'created_at', 'last_message_at']
    list_filter = ['is_active', 'conversation_type', 'preserve_context', 'created_at']
    search_fields = ['user__phone_number', 'user__full_name', 'thread_id', 'fixture_id']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (_('Información básica'), {
            'fields': ('user', 'thread_id', 'is_active', 'conversation_type')
        }),
        (_('Contexto y datos'), {
            'fields': ('fixture_id', 'preserve_context')
        }),
        (_('Fechas'), {
            'fields': ('created_at', 'updated_at', 'last_message_at')
        }),
    )
    
    inlines = [MessageInline]
    
    readonly_fields = ['created_at', 'updated_at', 'last_message_at']
    
    actions = ['mark_as_active', 'mark_as_inactive', 'mark_as_preserve_context', 'mark_as_no_preserve_context']
    
    def mark_as_active(self, request, queryset):
        queryset.update(is_active=True)
    mark_as_active.short_description = _("Marcar como activas")
    
    def mark_as_inactive(self, request, queryset):
        queryset.update(is_active=False)
    mark_as_inactive.short_description = _("Marcar como inactivas")
    
    def mark_as_preserve_context(self, request, queryset):
        queryset.update(preserve_context=True)
    mark_as_preserve_context.short_description = _("Preservar contexto")
    
    def mark_as_no_preserve_context(self, request, queryset):
        queryset.update(preserve_context=False)
    mark_as_no_preserve_context.short_description = _("No preservar contexto")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'conversation_info', 'is_from_user', 'message_type', 
                    'content_preview', 'has_json_data', 'created_at']
    list_filter = ['is_from_user', 'message_type', 'created_at']
    search_fields = ['content', 'conversation__user__phone_number']
    date_hierarchy = 'created_at'
    
    readonly_fields = ['conversation', 'created_at', 'request_json', 'response_json']
    
    fieldsets = (
        (_('Información básica'), {
            'fields': ('conversation', 'message_id', 'is_from_user', 'message_type', 'created_at')
        }),
        (_('Contenido'), {
            'fields': ('content',)
        }),
        (_('Datos JSON'), {
            'fields': ('request_json', 'response_json'),
            'classes': ('collapse',),
        }),
    )
    
    def conversation_info(self, obj):
        return f"{obj.conversation.user} - Conv #{obj.conversation.id}"
    conversation_info.short_description = _("Conversación")
    
    def content_preview(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_preview.short_description = _("Contenido")
    
    def has_json_data(self, obj):
        has_request = obj.request_json is not None
        has_response = obj.response_json is not None
        
        if has_request and has_response:
            return format_html('<span style="color: green;">✓</span> (Ambos)')
        elif has_request:
            return format_html('<span style="color: blue;">✓</span> (Solicitud)')
        elif has_response:
            return format_html('<span style="color: orange;">✓</span> (Respuesta)')
        else:
            return format_html('<span style="color: red;">✗</span>')
    has_json_data.short_description = _("Datos JSON")


@admin.register(UserInput)
class UserInputAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'flow_id', 'screen_id', 'created_at']
    list_filter = ['flow_id', 'screen_id', 'created_at']
    search_fields = ['user__phone_number', 'flow_id', 'screen_id']
    date_hierarchy = 'created_at'
    
    readonly_fields = ['user', 'flow_id', 'flow_token', 'screen_id', 'data', 'created_at']


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'language', 'updated_at']
    list_filter = ['language', 'updated_at']
    search_fields = ['user__phone_number', 'user__full_name']
    
    readonly_fields = ['user', 'updated_at']
    
    fieldsets = (
        (_('Usuario'), {
            'fields': ('user',)
        }),
        (_('Preferencias'), {
            'fields': ('language', 'favorite_teams', 'favorite_leagues', 'notification_preferences')
        }),
        (_('Fechas'), {
            'fields': ('updated_at',)
        }),
    )


@admin.register(AssistantConfig)
class AssistantConfigAdmin(admin.ModelAdmin):
    list_display = ['user', 'assistant_name', 'language_style', 'experience_level', 'updated_at']
    list_filter = ['language_style', 'experience_level', 'updated_at']
    search_fields = ['user__phone_number', 'user__full_name', 'assistant_name']
    
    readonly_fields = ['user', 'updated_at']
    
    fieldsets = (
        (_('Usuario'), {
            'fields': ('user',)
        }),
        (_('Configuración del Asistente'), {
            'fields': ('assistant_name', 'language_style', 'experience_level')
        }),
        (_('Preferencias de Predicciones'), {
            'fields': ('prediction_types',)
        }),
        (_('Configuración Adicional'), {
            'fields': ('custom_settings',)
        }),
        (_('Fechas'), {
            'fields': ('updated_at',)
        }),
    )
