# Deep90 WhatsApp API Integration

Esta aplicación implementa la integración de Deep90 con la API de WhatsApp Business y el Asistente de OpenAI para proporcionar un servicio de consulta de datos deportivos a través de WhatsApp.

## Características principales

- 📱 **Webhook de WhatsApp**: Recibe y procesa mensajes de usuarios de WhatsApp.
- 🤖 **Asistente con IA**: Integración con OpenAI Assistant para responder consultas sobre fútbol.
- 📊 **Consulta de datos deportivos**: Conexión con la app sports_data para consultar información de partidos, resultados y clasificaciones.
- 👤 **Gestión de usuarios**: Sistema completo de gestión de usuarios de WhatsApp.
- 💬 **Historial de conversaciones**: Almacenamiento y gestión de conversaciones y mensajes.
- 📝 **Formularios interactivos**: Integración con flujos de formularios de WhatsApp para registro de usuarios.
- 💲 **Sistema de suscripciones**: Diferentes niveles de acceso basados en planes de suscripción.

## Estructura de la aplicación

- **models.py**: Define los modelos de datos para usuarios, conversaciones, mensajes y preferencias.
- **views.py**: Implementa las vistas que manejan los webhooks de WhatsApp y OpenAI Assistant.
- **services.py**: Servicios para comunicarse con la API de WhatsApp Business y OpenAI.
- **tasks.py**: Tareas Celery para procesamiento asíncrono de mensajes y respuestas.
- **assistant_manager.py**: Gestiona la interacción con OpenAI Assistant.
- **sports_service.py**: Servicios para consultar datos deportivos desde la app sports_data.
- **admin.py**: Configuración del panel de administración para los modelos.
- **urls.py**: Define las rutas URL para los webhooks.

## Webhooks disponibles

- `/whatsapp/webhook/`: Webhook principal para comunicación con WhatsApp Business API.
- `/whatsapp/assistant-webhook/`: Webhook para recibir eventos de OpenAI Assistant.
- `/whatsapp/flow-webhook/`: Webhook para recibir datos de formularios de WhatsApp.

## Configuración

La aplicación requiere las siguientes variables de entorno:

```
WHATSAPP_VERIFY_TOKEN=your_verify_token
WHATSAPP_ACCESS_TOKEN=your_access_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
WHATSAPP_VERSION_API=v22.0
WHATSAPP_FLOW_SIGN_UP=your_flow_id
WHATSAPP_FLOW_MODE=your_flow_mode
WHATSAPP_FLOW_VERSION_MESSAGES=v22.0

OPENAI_API_KEY=your_openai_api_key
ASSISTANT_ID_FREE=your_free_assistant_id
ASSISTANT_ID_PAY=your_paid_assistant_id
```

## Modelo de datos

### WhatsAppUser
Almacena la información de los usuarios de WhatsApp.

### Conversation
Representa una conversación entre un usuario y el asistente.

### Message
Representa un mensaje individual dentro de una conversación.

### UserInput
Almacena datos enviados por usuarios a través de formularios interactivos de WhatsApp.

### UserPreference
Guarda las preferencias del usuario como equipos favoritos, idioma, etc.

## Flujo de comunicación

1. Usuario envía mensaje a través de WhatsApp
2. Meta/WhatsApp envía una notificación al webhook
3. El webhook procesa el mensaje y lo envía a una tarea Celery
4. La tarea Celery identifica al usuario y determina la acción a realizar
5. Si el mensaje es para el asistente, se envía a OpenAI Assistant
6. El asistente procesa el mensaje y puede llamar a herramientas (tools)
7. Las herramientas consultan datos deportivos según sea necesario
8. La respuesta se envía de vuelta al usuario a través de la API de WhatsApp

## Uso

Para usar esta app, se requiere tener:

1. Una cuenta en WhatsApp Business Platform
2. Un número de teléfono verificado en WhatsApp Business
3. Una cuenta en OpenAI con acceso a la API de Asistentes
4. Asistentes configurados en OpenAI con las herramientas apropiadas

## Funciones del asistente

El asistente puede utilizar las siguientes herramientas:

- `get_football_fixtures`: Obtiene los próximos partidos de fútbol
- `get_football_results`: Obtiene los resultados recientes de partidos
- `get_football_standings`: Obtiene la clasificación actual de una liga

## Desarrollo

Para desarrollar esta aplicación, asegúrate de tener configuradas todas las variables de entorno necesarias y de tener acceso a las APIs requeridas.