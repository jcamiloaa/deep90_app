from django.urls import path
from .views import (
    WhatsAppWebhookView, 
    AssistantWebhookView, 
    WhatsAppFlowWebhookView, 
    FootballFlowDataView,
    whatsapp_flow_football,
    AssistantConfigFlowDataView,
    whatsapp_flow_assistant_config,
    AssistantConfigSaveView,
    UpdateDataFlowDataView,
    whatsapp_flow_update_data,
    UpdateDataSaveView
)

app_name = "whatsapp"

urlpatterns = [
    # Webhook para mensajes y eventos de WhatsApp
    path("webhook/", WhatsAppWebhookView.as_view(), name="webhook"),
    
    # Webhook para eventos del Asistente de OpenAI
    path("assistant-webhook/", AssistantWebhookView.as_view(), name="assistant-webhook"),
    
    # Webhook para datos de flujos completados
    path("flow-webhook/", WhatsAppFlowWebhookView.as_view(), name="flow-webhook"),
    
    # Endpoint para datos del flujo de fútbol
    path("football-flow-data/", FootballFlowDataView.as_view(), name="football-flow-data"),
    
    # Endpoint para servir el JSON del flujo según la documentación de Meta
    path("flow/football/", whatsapp_flow_football, name="flow-football"),
    
    # Endpoint para datos del flujo de configuración de asistente
    path("assistant-config-flow-data/", AssistantConfigFlowDataView.as_view(), name="assistant-config-flow-data"),
    
    # Endpoint para servir el JSON del flujo de configuración de asistente
    path("flow/assistant-config/", whatsapp_flow_assistant_config, name="flow-assistant-config"),
    
    # Endpoint para guardar la configuración personalizada del asistente
    path("assistant-config/save/", AssistantConfigSaveView.as_view(), name="assistant-config-save"),
    
    # Endpoint para datos del flujo de actualización de datos de usuario
    path("update-data-flow-data/", UpdateDataFlowDataView.as_view(), name="update-data-flow-data"),
    
    # Endpoint para servir el JSON del flujo de actualización de datos
    path("flow/update-data/", whatsapp_flow_update_data, name="flow-update-data"),
    
    # Endpoint para guardar los datos actualizados del usuario
    path("update-data/save/", UpdateDataSaveView.as_view(), name="update-data-save"),
]

