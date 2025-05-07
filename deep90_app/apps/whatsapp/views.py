import json
import logging
import traceback
import hmac
import hashlib
from django.http import HttpResponse, JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.conf import settings
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from .services import WhatsAppService, OpenAIAssistantService
from .models import WhatsAppUser, Conversation, Message, WhatsAppUserStatus, UserInput, AssistantConfig
from .tasks import process_whatsapp_message, process_assistant_response
from ..sports_data.models import LiveFixtureData
from .flows import FootballDataFlow
from .flows_config import ASSISTANT_CONFIG_FLOW_JSON

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class WhatsAppWebhookView(View):
    """
    Vista para manejar el webhook de WhatsApp.
    
    GET: Verificación del webhook
    POST: Recepción de eventos/mensajes
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.whatsapp_service = WhatsAppService()
    
    def get(self, request, *args, **kwargs):
        """
        Maneja la verificación del webhook por parte de WhatsApp.
        
        WhatsApp envía una solicitud GET con parámetros específicos para verificar el webhook.
        """
        try:
            # Extraer parámetros de la solicitud
            mode = request.GET.get('hub.mode')
            token = request.GET.get('hub.verify_token')
            challenge = request.GET.get('hub.challenge')
            
            # Verificar el webhook usando el servicio
            challenge_response = self.whatsapp_service.verify_webhook(mode, token, challenge)
            
            if challenge_response:
                # Si la verificación es exitosa, devolvemos el challenge
                return HttpResponse(challenge_response)
            else:
                # Si la verificación falla, devolvemos 403 Forbidden
                return HttpResponse("Verification failed", status=403)
        
        except Exception as e:
            logger.error(f"Error during webhook verification: {e}")
            return HttpResponse("Error", status=500)
    
    def post(self, request, *args, **kwargs):
        """
        Maneja eventos y mensajes entrantes de WhatsApp.
        """
        try:
            # Parsear el cuerpo de la solicitud
            body_unicode = request.body.decode('utf-8')
            webhook_data = json.loads(body_unicode)
            
            logger.debug(f"Webhook data: {webhook_data}")
            
            # Verificar si son datos de mensajería de WhatsApp
            if 'entry' in webhook_data and webhook_data['entry']:
                # Procesar cada entrada (puede haber varias)
                for entry in webhook_data['entry']:
                    # Verificar si hay cambios en mensajería
                    if 'changes' in entry and entry['changes']:
                        for change in entry['changes']:
                            # Verificar si es una notificación de WhatsApp
                            if change.get('field') == 'messages':
                                value = change.get('value', {})
                                
                                # Manejar diferentes tipos de eventos
                                if 'messages' in value:
                                    # Evento de mensajes
                                    self._handle_messages(value)
                                elif 'statuses' in value:
                                    # Evento de estado de mensaje
                                    self._handle_statuses(value)
                                elif 'contacts' in value:
                                    # Información de contacto sin mensaje
                                    pass
                                
            # Responder exitosamente al webhook
            return HttpResponse("EVENT_RECEIVED", status=200)
        
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            logger.error(traceback.format_exc())
            # Aún respondemos OK para que WhatsApp no reintente continuamente
            return HttpResponse("EVENT_RECEIVED", status=200)
    
    def _handle_messages(self, value):
        """
        Maneja mensajes entrantes de WhatsApp.
        
        Args:
            value: Diccionario con los datos del mensaje
        """
        messages = value.get('messages', [])
        contacts = value.get('contacts', [])
        
        if not messages or not contacts:
            logger.warning("Missing messages or contacts in webhook data")
            return
        
        for message in messages:
            # Verificar que tenemos el ID del mensaje
            if 'id' not in message:
                continue
            
            # Encontrar el contacto correspondiente
            contact = next((c for c in contacts if c.get('wa_id')), None)
            if not contact:
                logger.warning(f"Contact not found for message {message.get('id')}")
                continue

            # Log the message directly to ensure it's stored even if async processing fails
            try:
                wa_id = contact.get('wa_id')
                message_id = message.get('id')
                message_type = message.get('type', 'unknown')
                
                # Get message content based on type
                content = ""
                if message_type == 'text':
                    content = message.get('text', {}).get('body', '')
                elif message_type == 'interactive':
                    interactive_data = message.get('interactive', {})
                    interactive_type = interactive_data.get('type')
                    if interactive_type == 'button_reply':
                        button_id = interactive_data.get('button_reply', {}).get('id')
                        button_title = interactive_data.get('button_reply', {}).get('title', '')
                        content = f"Button: {button_title} ({button_id})"
                    elif interactive_type == 'list_reply':
                        list_id = interactive_data.get('list_reply', {}).get('id')
                        list_title = interactive_data.get('list_reply', {}).get('title', '')
                        content = f"List: {list_title} ({list_id})"
                    else:
                        content = f"Interactive ({interactive_type})"
                elif message_type == 'location':
                    location_data = message.get('location', {})
                    latitude = location_data.get('latitude')
                    longitude = location_data.get('longitude')
                    content = f"Location: {latitude}, {longitude}"
                else:
                    content = f"Message of type {message_type}"
                
                # Prepare the complete webhook data for storage
                # We use the full message and add the contact info for context
                webhook_data = {
                    'message': message,
                    'contact': contact
                }
                
                # Log the incoming message with complete JSON
                self.whatsapp_service.log_message(
                    wa_id, 
                    content, 
                    message_type, 
                    True,  # is_from_user=True
                    message_id,
                    request_json=webhook_data,  # Store complete webhook data
                    response_json=None  # No response for incoming messages
                )
            except Exception as e:
                logger.error(f"Error logging incoming message: {e}")
            
            # Encolar tarea para procesar el mensaje en background con Celery
            process_whatsapp_message.delay(contact, message)
    
    def _handle_statuses(self, value):
        """
        Maneja actualizaciones de estado de mensajes enviados.
        
        Args:
            value: Diccionario con los datos de estado
        """
        statuses = value.get('statuses', [])
        
        if not statuses:
            return
        
        for status in statuses:
            status_type = status.get('status')
            message_id = status.get('id')
            
            # Aquí podríamos actualizar el estado de los mensajes en la base de datos
            # Por ahora solo registramos en log
            logger.info(f"Message {message_id} status: {status_type}")


@method_decorator(csrf_exempt, name='dispatch')
class AssistantWebhookView(View):
    """
    Vista para manejar el webhook del Asistente de OpenAI.
    
    POST: Recepción de eventos de finalización del asistente
    """
    
    def post(self, request, *args, **kwargs):
        """
        Maneja eventos de finalización del asistente.
        """
        try:
            # Parsear el cuerpo de la solicitud
            body_unicode = request.body.decode('utf-8')
            webhook_data = json.loads(body_unicode)
            
            logger.debug(f"Assistant webhook data: {webhook_data}")
            
            # Verificar el tipo de evento
            event_type = webhook_data.get('type')
            
            if event_type == 'thread.run.completed':
                # Evento de run completado
                thread_id = webhook_data.get('data', {}).get('thread_id')
                run_id = webhook_data.get('data', {}).get('id')
                
                if thread_id and run_id:
                    # Encolar tarea para procesar la respuesta del asistente
                    process_assistant_response.delay(thread_id, run_id)
                else:
                    logger.warning("Missing thread_id or run_id in assistant webhook data")
            
            # Responder exitosamente al webhook
            return JsonResponse({"status": "success"})
        
        except Exception as e:
            logger.error(f"Error processing assistant webhook: {e}")
            logger.error(traceback.format_exc())
            return JsonResponse({"status": "error", "message": str(e)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class WhatsAppFlowWebhookView(View):
    """
    Vista para manejar el webhook de flujos de WhatsApp.
    
    POST: Recepción de datos de formularios completados
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.whatsapp_service = WhatsAppService()
    
    def post(self, request, *args, **kwargs):
        """
        Maneja la recepción de datos de formularios completados en WhatsApp.
        """
        try:
            # Parsear el cuerpo de la solicitud
            body_unicode = request.body.decode('utf-8')
            flow_data = json.loads(body_unicode)
            
            logger.debug(f"Flow webhook data: {flow_data}")
            
            # Extraer datos importantes
            flow_token = flow_data.get('flow_token')
            flow_id = flow_data.get('flow_id')
            wa_id = flow_data.get('wa_id')
            screen_id = flow_data.get('screen_id')
            input_data = flow_data.get('input_data', {})
            
            if not all([flow_token, flow_id, wa_id]):
                return JsonResponse({"status": "error", "message": "Missing required fields"}, status=400)
            
            # Buscar o crear el usuario
            whatsapp_user, created = WhatsAppUser.objects.get_or_create(
                phone_number=wa_id,
                defaults={'status': WhatsAppUserStatus.NEW}
            )
            
            # Guardar los datos del formulario
            user_input = UserInput.objects.create(
                user=whatsapp_user,
                flow_id=flow_id,
                flow_token=flow_token,
                screen_id=screen_id,
                data=input_data
            )
            
            # También guardar como mensaje con el JSON completo para trazabilidad
            content = f"Flow Input - Screen: {screen_id}"
            self.whatsapp_service.log_message(
                wa_id,
                content,
                'flow_input',
                True,  # is_from_user=True
                None,  # no message_id for flows
                request_json=flow_data,
                response_json={"status": "success"}
            )
            
            # Procesar los datos del formulario según el flujo y la pantalla
            if flow_id == settings.WHATSAPP_FLOW_SIGN_UP:
                self._process_signup_data(whatsapp_user, input_data, screen_id)
            elif flow_id == settings.WHATSAPP_FLOW_CONFIG_ANALYTICS:
                self._process_assistant_config_data(whatsapp_user, input_data, screen_id)
            
            # Responder exitosamente
            return JsonResponse({"status": "success"})
        
        except Exception as e:
            logger.error(f"Error processing flow webhook: {e}")
            logger.error(traceback.format_exc())
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
    
    def _process_signup_data(self, user, data, screen_id):
        """
        Procesa los datos del formulario de registro.
        
        Args:
            user: Objeto WhatsAppUser
            data: Diccionario con los datos del formulario
            screen_id: ID de la pantalla actual
        """
        # Procesar datos según la pantalla
        if screen_id == 'personal_info':
            # Actualizar información personal
            if 'full_name' in data:
                user.full_name = data['full_name']
            if 'email' in data:
                user.email = data['email']
            if 'birth_date' in data:
                try:
                    user.birth_date = data['birth_date']
                except:
                    pass
            
            # Cambiar estado a registrado si tenemos la información básica
            if user.full_name and user.email:
                user.status = WhatsAppUserStatus.REGISTERED
            
            user.save()

    def _process_assistant_config_data(self, user, data, screen_id):
        """
        Procesa los datos del formulario de configuración de asistente.
        
        Args:
            user: Objeto WhatsAppUser
            data: Diccionario con los datos del formulario
            screen_id: ID de la pantalla actual
        """
        logger.debug(f"Procesando datos de configuración de asistente: {data}")
        
        # Obtener o crear la configuración del asistente para este usuario
        assistant_config, created = AssistantConfig.objects.get_or_create(user=user)
        
        # Al completar el flujo, guardar todos los datos
        if screen_id == 'SUMMARY':
            logger.info(f"Actualizando configuración completa para usuario {user.phone_number}")
            
            # Actualizar todos los campos con los datos recibidos
            if 'assistant_name' in data:
                assistant_config.assistant_name = data['assistant_name']
            
            if 'language_style' in data:
                assistant_config.language_style = data['language_style']
            
            if 'experience_level' in data:
                assistant_config.experience_level = data['experience_level']
            
            if 'prediction_types' in data:
                prediction_types = data['prediction_types']
                # Si es string, convertir a lista
                if isinstance(prediction_types, str):
                    assistant_config.prediction_types = [prediction_types]
                else:
                    assistant_config.prediction_types = prediction_types
            
            # Guardar la configuración
            assistant_config.save()
            
            # Enviar mensaje de confirmación al usuario
            try:
                self.whatsapp_service.send_text_message(
                    user.phone_number, 
                    f"✅ ¡Tu asistente ha sido personalizado!\n\n"
                    f"*Nombre:* {assistant_config.assistant_name}\n"
                    f"*Estilo:* {'Técnico' if assistant_config.language_style == 'tecnico' else 'Normal'}\n"
                    f"*Experiencia:* {'Alta' if assistant_config.experience_level == 'alta' else ('Media' if assistant_config.experience_level == 'media' else 'Baja')}\n"
                    f"*Tipos de predicciones:* {', '.join(assistant_config.prediction_types if isinstance(assistant_config.prediction_types, list) else [assistant_config.prediction_types])}\n\n"
                    f"Ahora puedes hablar con tu asistente personalizado y te responderá según tus preferencias."
                )
                logger.info(f"Mensaje de confirmación enviado a {user.phone_number}")
            except Exception as e:
                logger.error(f"Error al enviar mensaje de confirmación: {str(e)}")
        
        # Solo para depuración durante el desarrollo
        else:
            logger.debug(f"Recibidos datos parciales de pantalla {screen_id}: {data}")
            
        return assistant_config


class FootballFlowDataView(View):
    """
    Vista para manejar el endpoint del flujo de consulta de datos de fútbol.
    
    Esta vista se integra con WhatsApp Flows para permitir a los usuarios
    navegar y consultar datos de partidos de fútbol de forma interactiva.
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.whatsapp_service = WhatsAppService()
    
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        """
        Maneja las solicitudes POST del flujo de WhatsApp.
        
        Descifra los datos, procesa la selección del usuario y devuelve
        la siguiente pantalla cifrada.
        """
        logger.info("-----------------------------------------------------")
        logger.info("Processing Football Flow Data View")
        logger.info(f"Request body: {request.body}")
        logger.info(f"Request headers: {request.headers}")
        logger.info(f"Request method: {request.method}")
        logger.info(f"Request path: {request.path}")

        try:
            # Parsear el cuerpo de la solicitud
            body = json.loads(request.body)
            
            # Leer los campos de la solicitud
            encrypted_flow_data_b64 = body.get('encrypted_flow_data')
            encrypted_aes_key_b64 = body.get('encrypted_aes_key')
            initial_vector_b64 = body.get('initial_vector')
            
            if not all([encrypted_flow_data_b64, encrypted_aes_key_b64, initial_vector_b64]):
                logger.error("Falta algún campo requerido en la solicitud de flujo")
                return HttpResponse(status=421)  # Return proper error code as per documentation
            
            # Descifrar los datos del flujo
            from .crypto import decrypt_request, encrypt_response
            try:
                decrypted_data, aes_key, iv = decrypt_request(
                    encrypted_flow_data_b64, encrypted_aes_key_b64, initial_vector_b64
                )
            except Exception as e:
                logger.error(f"Error al descifrar el mensaje: {e}")
                return HttpResponse(status=421)  # Return proper error code for decryption failures
            
            logger.debug(f"Datos descifrados: {decrypted_data}")
            
            # Utilizar la clase FootballDataFlow para manejar la solicitud y obtener la respuesta
            from .flows import FootballDataFlow
            response_data = FootballDataFlow.handle_flow_request(decrypted_data)
            
            # Intentar extraer información de identificación del usuario para registro
            try:
                if 'wa_id' in decrypted_data:
                    wa_id = decrypted_data.get('wa_id')
                    
                    # Guardar el JSON de la solicitud y respuesta para trazabilidad
                    screen_id = decrypted_data.get('screen', 'unknown')
                    content = f"Football Flow Data - Screen: {screen_id}"
                    
                    # Almacenar datos de la solicitud y respuesta
                    self.whatsapp_service.log_message(
                        wa_id,
                        content,
                        'football_flow',
                        True,  # is_from_user=True para la solicitud
                        None,  # no message_id para flows
                        request_json=decrypted_data
                    )
                    
                    # Registrar también la respuesta como mensaje del sistema
                    self.whatsapp_service.log_message(
                        wa_id,
                        f"Football Flow Response - Screen: {response_data.get('screen', 'unknown')}",
                        'football_flow_response',
                        False,  # is_from_user=False para la respuesta
                        None,   # no message_id para la respuesta
                        request_json=None,
                        response_json=response_data
                    )
            except Exception as e:
                logger.error(f"Error al guardar datos de flujo de fútbol: {e}")
            
            # Cifrar y devolver la respuesta
            encrypted_response = encrypt_response(response_data, aes_key, iv)
            return HttpResponse(encrypted_response, content_type='text/plain')
            
        except Exception as e:
            logger.error(f"Error procesando solicitud de flujo de fútbol: {e}")
            logger.error(traceback.format_exc())
            return HttpResponse(status=421)  # Return proper error code for general errors


@csrf_exempt
@require_http_methods(["GET", "POST"])
def whatsapp_webhook(request):
    """
    Endpoint para recibir y procesar los webhooks de WhatsApp.
    """
    if request.method == "GET":
        # Verificación del webhook por parte de WhatsApp
        verify_token = request.GET.get("hub.verify_token")
        if verify_token == settings.WHATSAPP_VERIFY_TOKEN:
            return HttpResponse(request.GET.get("hub.challenge"))
        return HttpResponse("Invalid verification token", status=403)
    
    elif request.method == "POST":
        # Procesar mensajes entrantes
        try:
            data = json.loads(request.body)
            logger.info(f"Webhook data received: {data}")
            # Aquí iría la lógica para procesar los mensajes
            return HttpResponse("Message received")
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            return HttpResponse("Error processing webhook", status=500)


@csrf_exempt
@require_http_methods(["GET"])
def whatsapp_flow_football(request):
    """
    Endpoint para servir el JSON del flujo de WhatsApp para consultas de fútbol.
    
    Este endpoint sigue el formato requerido por Meta para WhatsApp Flows.
    
    Returns:
        JsonResponse: El JSON completo del flujo de WhatsApp.
    """
    try:
        # Generar el JSON del flujo
        flow_json = FootballDataFlow.generate_flow_json()
        
        # Verificar firma si está configurado para producción
        if settings.WHATSAPP_FLOW_MODE == "production":
            # Aquí se implementaría la verificación de la firma
            pass
        
        # Retornar el JSON del flujo
        return JsonResponse(flow_json)
    except Exception as e:
        logger.error(f"Error generating flow JSON: {e}")
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def whatsapp_flow_assistant_config(request):
    """Devuelve el JSON del flujo de configuración de asistente personalizado."""
    return JsonResponse(ASSISTANT_CONFIG_FLOW_JSON, safe=False)

class AssistantConfigFlowDataView(View):
    """
    Vista para manejar el endpoint del flujo de configuración del asistente.
    
    Esta vista se integra con WhatsApp Flows para permitir a los usuarios
    personalizar su experiencia con el asistente de forma interactiva.
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.whatsapp_service = WhatsAppService()
    
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get(self, request, *args, **kwargs):
        """
        Maneja solicitudes GET para verificación o healthcheck.
        """
        logger.debug("Recibida solicitud GET en AssistantConfigFlowDataView")
        return JsonResponse({"status": "ok"})
    
    def post(self, request, *args, **kwargs):
        """
        Maneja las solicitudes POST del flujo de WhatsApp.
        
        Descifra los datos, procesa la selección del usuario y devuelve
        la siguiente pantalla cifrada.
        """
        logger.info("-----------------------------------------------------")
        logger.info("Processing Assistant Config Flow Data View")
        logger.info(f"Request body: {request.body}")
        logger.info(f"Request headers: {request.headers}")
        logger.info(f"Request method: {request.method}")
        logger.info(f"Request path: {request.path}")
        
        try:
            # Parsear el cuerpo de la solicitud
            body = json.loads(request.body)
            
            # Leer los campos de la solicitud
            encrypted_flow_data_b64 = body.get('encrypted_flow_data')
            encrypted_aes_key_b64 = body.get('encrypted_aes_key')
            initial_vector_b64 = body.get('initial_vector')
            
            if not all([encrypted_flow_data_b64, encrypted_aes_key_b64, initial_vector_b64]):
                logger.error("Falta algún campo requerido en la solicitud de flujo de configuración de asistente")
                return HttpResponse(status=421)  # Return proper error code as per documentation
            
            # Descifrar los datos del flujo
            from .crypto import decrypt_request, encrypt_response
            try:
                decrypted_data, aes_key, iv = decrypt_request(
                    encrypted_flow_data_b64, encrypted_aes_key_b64, initial_vector_b64
                )
            except Exception as e:
                logger.error(f"Error al descifrar el mensaje: {e}")
                return HttpResponse(status=421)  # Return proper error code for decryption failures
            
            logger.debug(f"Datos descifrados: {decrypted_data}")
            
            # Leer los data-source dinámicos desde settings
            try:
                data_source_1 = json.loads(getattr(settings, 'DATA_SOURCE_CONFIG_ANALYTICS_1', '[]'))
                logger.debug(f"DATA_SOURCE_CONFIG_ANALYTICS_1 cargado: {data_source_1}")
            except Exception as e:
                logger.error(f"Error al cargar DATA_SOURCE_CONFIG_ANALYTICS_1: {str(e)}")
                data_source_1 = [
                    {"id": "normal", "title": "Lenguaje sencillo"},
                    {"id": "tecnico", "title": "Técnico y analítico"}
                ]
            
            try:
                data_source_2 = json.loads(getattr(settings, 'DATA_SOURCE_CONFIG_ANALYTICS_2', '[]'))
                logger.debug(f"DATA_SOURCE_CONFIG_ANALYTICS_2 cargado: {data_source_2}")
            except Exception as e:
                logger.error(f"Error al cargar DATA_SOURCE_CONFIG_ANALYTICS_2: {str(e)}")
                data_source_2 = [
                    {"id": "baja", "title": "Principiante"},
                    {"id": "media", "title": "Intermedio"},
                    {"id": "alta", "title": "Avanzado"}
                ]
                
            try:
                data_source_3 = json.loads(getattr(settings, 'DATA_SOURCE_CONFIG_ANALYTICS_3', '[]'))
                logger.debug(f"DATA_SOURCE_CONFIG_ANALYTICS_3 cargado: {data_source_3}")
            except Exception as e:
                logger.error(f"Error al cargar DATA_SOURCE_CONFIG_ANALYTICS_3: {str(e)}")
                data_source_3 = [
                    {"id": "resultado", "title": "Resultado del partido"},
                    {"id": "goles", "title": "Cantidad de goles"},
                    {"id": "cuotas", "title": "Cuotas y apuestas"},
                    {"id": "jugadores", "title": "Rendimiento de jugadores"}
                ]

            # Cargar el JSON base del flujo
            from .flows_config import ASSISTANT_CONFIG_FLOW_JSON
            flow_json = json.loads(json.dumps(ASSISTANT_CONFIG_FLOW_JSON))  # deep copy

            # Extraer información importante
            action = decrypted_data.get('action', '').lower()
            screen = decrypted_data.get('screen', '')
            data = decrypted_data.get('data', {})
            flow_token = decrypted_data.get('flowToken') or decrypted_data.get('flow_token')
            wa_id = decrypted_data.get('wa_id')
            
            # Variables para almacenar la configuración existente del usuario
            existing_config = None
            if wa_id:
                try:
                    user = WhatsAppUser.objects.get(phone_number=wa_id)
                    existing_config = AssistantConfig.objects.filter(user=user).first()
                    logger.debug(f"Configuración existente para usuario {wa_id}: {existing_config}")
                except Exception as e:
                    logger.debug(f"No se encontró configuración para usuario {wa_id}: {str(e)}")
            
            # Manejar la acción de ping (health check)
            if action == 'ping':
                logger.debug("Manejando solicitud de ping (health check)")
                response_data = {
                    "data": {
                        "status": "active"
                    }
                }
                encrypted_response = encrypt_response(response_data, aes_key, iv)
                return HttpResponse(encrypted_response, content_type='text/plain')
            
            # Manejar la acción INIT - Mostrar pantalla de bienvenida
            if action == 'init':
                logger.debug("Manejando acción INIT - Mostrando pantalla de bienvenida")
                response_data = {
                    "screen": "WELCOME",
                    "data": {
                        "message": "¡Bienvenido al asistente de configuración de Deep90 AI!"
                    }
                }
                
                # Incluir el token de flujo si está disponible
                if flow_token:
                    response_data["flow_token"] = flow_token
                
                logger.debug(f"Enviando respuesta INIT: {response_data}")
                
                # Registrar la interacción para trazabilidad
                self._log_interaction(wa_id, "INIT", decrypted_data, response_data)
                
                # Cifrar y devolver la respuesta
                encrypted_response = encrypt_response(response_data, aes_key, iv)
                return HttpResponse(encrypted_response, content_type='text/plain')
            
            # Manejar intercambio de datos entre pantallas
            if action == 'data_exchange':
                logger.debug(f"Manejando acción data_exchange para pantalla: {screen}")
                
                if screen == 'WELCOME':
                    # Pasar a la pantalla de configuración de personalidad
                    response_data = {
                        "screen": "CONFIG_PERSONALITY",
                        "data": {
                            # Añadir los arrays de datos para los RadioButtonsGroup
                            "language_styles": data_source_1,
                            "experience_levels": data_source_2
                        }
                    }
                    
                    # Prellenar con datos existentes si están disponibles
                    if existing_config:
                        logger.debug(f"Prellenando datos de personalidad con configuración existente")
                        response_data["data"]["assistant_name"] = existing_config.assistant_name
                        response_data["data"]["language_style"] = existing_config.language_style
                        response_data["data"]["experience_level"] = existing_config.experience_level
                    
                    # Incluir el token de flujo
                    if flow_token:
                        response_data["flow_token"] = flow_token
                
                elif screen == 'CONFIG_PERSONALITY':
                    # Extraer datos de la personalidad del asistente
                    assistant_name = self._extract_form_value(data, 'assistant_name', 'personality_form.assistant_name')
                    language_style = self._extract_form_value(data, 'language_style', 'personality_form.language_style')
                    experience_level = self._extract_form_value(data, 'experience_level', 'personality_form.experience_level')
                    
                    logger.debug(f"Datos extraídos: nombre={assistant_name}, estilo={language_style}, experiencia={experience_level}")
                    
                    # Pasar a la pantalla de preferencias de predicción
                    response_data = {
                        "screen": "CONFIG_PREFERENCES",
                        "data": {
                            "assistant_name": assistant_name,
                            "language_style": language_style,
                            "experience_level": experience_level,
                            "prediction_types": data_source_3
                        }
                    }
                    
                    # Prellenar con tipos de predicción existentes si están disponibles
                    if existing_config and existing_config.prediction_types:
                        logger.debug(f"Prellenando tipos de predicción con configuración existente")
                        response_data["data"]["prediction_types"] = existing_config.prediction_types
                    
                    # Incluir el token de flujo
                    if flow_token:
                        response_data["flow_token"] = flow_token
                
                else:
                    # Pantalla no reconocida, volver a WELCOME
                    logger.warning(f"Pantalla no reconocida: {screen}")
                    response_data = {
                        "screen": "WELCOME",
                        "data": {
                            "message": "¡Bienvenido al asistente de configuración de Deep90 AI!"
                        }
                    }
                    if flow_token:
                        response_data["flow_token"] = flow_token
                
                # Registrar la interacción para trazabilidad
                self._log_interaction(wa_id, f"DATA_EXCHANGE_{screen}", decrypted_data, response_data)
                
                # Cifrar y devolver la respuesta
                encrypted_response = encrypt_response(response_data, aes_key, iv)
                return HttpResponse(encrypted_response, content_type='text/plain')
            
            # Manejar acción de completado (cuando el usuario finaliza el flujo)
            if action == 'complete':
                logger.debug(f"Manejando acción complete para pantalla: {screen}")
                
                if screen == 'CONFIG_PREFERENCES':
                    # Extraer todos los datos recopilados
                    assistant_name = data.get('assistant_name', 'Deep90 AI')
                    language_style = data.get('language_style', 'normal')
                    experience_level = data.get('experience_level', 'media')
                    prediction_types = self._extract_form_value(data, 'prediction_types', 'preferences_form.prediction_types')
                    
                    logger.debug(f"Configuración final: nombre={assistant_name}, estilo={language_style}, experiencia={experience_level}, tipos={prediction_types}")
                    
                    # Guardar la configuración si tenemos el ID del usuario
                    if wa_id:
                        try:
                            user, created = WhatsAppUser.objects.get_or_create(phone_number=wa_id)
                            assistant_config, created = AssistantConfig.objects.get_or_create(user=user)
                            
                            # Actualizar configuración
                            assistant_config.assistant_name = assistant_name
                            assistant_config.language_style = language_style
                            assistant_config.experience_level = experience_level
                            
                            # Asegurarse de que prediction_types es una lista
                            if isinstance(prediction_types, str):
                                prediction_types = [prediction_types]
                            assistant_config.prediction_types = prediction_types
                            assistant_config.save()
                            
                            logger.info(f"Configuración guardada para usuario {wa_id}")
                            
                            # Enviar mensaje de confirmación al usuario después de completar
                            try:
                                self.whatsapp_service.send_text_message(
                                    wa_id, 
                                    f"✅ ¡Tu asistente ha sido personalizado!\n\n"
                                    f"*Nombre:* {assistant_config.assistant_name}\n"
                                    f"*Estilo:* {'Técnico' if assistant_config.language_style == 'tecnico' else 'Normal'}\n"
                                    f"*Experiencia:* {'Alta' if assistant_config.experience_level == 'alta' else ('Media' if assistant_config.experience_level == 'media' else 'Baja')}\n"
                                    f"*Tipos de predicciones:* {', '.join(assistant_config.prediction_types if isinstance(assistant_config.prediction_types, list) else [assistant_config.prediction_types])}\n\n"
                                    f"Ahora puedes hablar con tu asistente personalizado y te responderá según tus preferencias."
                                )
                            except Exception as e:
                                logger.error(f"Error al enviar mensaje de confirmación: {str(e)}")
                            
                        except Exception as e:
                            logger.error(f"Error al guardar configuración: {str(e)}")
                    
                    # Preparar respuesta de éxito
                    response_data = {
                        "data": {
                            "extension_message_response": {
                                "params": {
                                    "flow_token": flow_token,
                                    "result": "completed",
                                    "prediction_types": prediction_types,
                                    "assistant_name": assistant_name,
                                    "language_style": language_style,
                                    "experience_level": experience_level,
                                    "flow_id": settings.WHATSAPP_FLOW_CONFIG_ANALYTICS
                                }
                            }
                        }
                    }
                else:
                    # Si no es CONFIG_PREFERENCES, simplemente confirmar completado
                    response_data = {
                        "data": {
                            "extension_message_response": {
                                "params": {
                                    "flow_token": flow_token,
                                    "result": "completed"
                                }
                            }
                        }
                    }
            
                # Registrar la interacción para trazabilidad
                self._log_interaction(wa_id, f"COMPLETE_{screen}", decrypted_data, response_data)
                
                # Cifrar y devolver la respuesta
                encrypted_response = encrypt_response(response_data, aes_key, iv)
                return HttpResponse(encrypted_response, content_type='text/plain')
            
            # Manejar acción de retroceso
            if action == 'back':
                logger.debug(f"Manejando acción back desde pantalla {screen}")
                
                if screen == 'CONFIG_PERSONALITY':
                    response_data = {
                        "screen": "WELCOME",
                        "data": {
                            "message": "¡Bienvenido al asistente de configuración de Deep90 AI!"
                        }
                    }
                elif screen == 'CONFIG_PREFERENCES':
                    # Volver a pantalla de personalidad conservando datos
                    assistant_name = data.get('assistant_name', 'Deep90 AI')
                    language_style = data.get('language_style', 'normal')
                    experience_level = data.get('experience_level', 'media')
                    
                    response_data = {
                        "screen": "CONFIG_PERSONALITY",
                        "data": {
                            "assistant_name": assistant_name,
                            "language_style": language_style,
                            "experience_level": experience_level
                        }
                    }
                else:
                    # Default a pantalla de bienvenida
                    response_data = {
                        "screen": "WELCOME",
                        "data": {
                            "message": "¡Bienvenido al asistente de configuración de Deep90 AI!"
                        }
                    }
                
                # Incluir el token de flujo
                if flow_token:
                    response_data["flow_token"] = flow_token
                
                # Registrar la interacción para trazabilidad
                self._log_interaction(wa_id, f"BACK_{screen}", decrypted_data, response_data)
                
                # Cifrar y devolver la respuesta
                encrypted_response = encrypt_response(response_data, aes_key, iv)
                return HttpResponse(encrypted_response, content_type='text/plain')
            
            # Para cualquier otra acción o si no se entiende, responder con pantalla de bienvenida
            logger.warning(f"Acción no reconocida: {action}")
            response_data = {
                "screen": "WELCOME",
                "data": {
                    "message": "¡Bienvenido al asistente de configuración de Deep90 AI!"
                }
            }
            
            # Incluir el token de flujo
            if flow_token:
                response_data["flow_token"] = flow_token
            
            # Cifrar y devolver la respuesta
            encrypted_response = encrypt_response(response_data, aes_key, iv)
            return HttpResponse(encrypted_response, content_type='text/plain')
            
        except Exception as e:
            logger.error(f"Error procesando solicitud de flujo de configuración: {e}")
            logger.error(traceback.format_exc())
            return HttpResponse(status=421)  # Return proper error code for general errors
    
    def _extract_form_value(self, data, field_name, fallback_path=None):
        """
        Extrae un valor de formulario de los datos, con soporte para diferentes formatos.
        
        Args:
            data: Diccionario de datos
            field_name: Nombre del campo a extraer
            fallback_path: Ruta alternativa (con notación de punto) para buscar
            
        Returns:
            El valor extraído o None si no se encuentra
        """
        # Intentar obtener directamente
        if field_name in data:
            value = data[field_name]
            if isinstance(value, list) and value:
                return value[0] if len(value) == 1 else value
            return value
        
        # Intentar con la ruta alternativa
        if fallback_path:
            parts = fallback_path.split('.')
            if len(parts) == 2 and parts[0] in data and isinstance(data[parts[0]], dict) and parts[1] in data[parts[0]]:
                value = data[parts[0]][parts[1]]
                if isinstance(value, list) and value:
                    return value[0] if len(value) == 1 else value
                return value
        
        # Buscar en cualquier formulario anidado
        for key, value in data.items():
            if isinstance(value, dict) and field_name in value:
                nested_value = value[field_name]
                if isinstance(nested_value, list) and nested_value:
                    return nested_value[0] if len(nested_value) == 1 else nested_value
                return nested_value
        
        return None
    
    def _log_interaction(self, wa_id, action_type, request_data, response_data):
        """
        Registra la interacción para trazabilidad.
        
        Args:
            wa_id: ID de WhatsApp del usuario
            action_type: Tipo de acción (INIT, DATA_EXCHANGE, etc.)
            request_data: Datos de la solicitud
            response_data: Datos de la respuesta
        """
        if not wa_id:
            logger.debug("No se pudo registrar interacción: falta wa_id")
            return
        
        try:
            self.whatsapp_service.log_message(
                wa_id,
                f"Assistant Config Flow - {action_type}",
                'assistant_config_flow',
                True,  # is_from_user=True para la solicitud
                None,  # no message_id para flows
                request_json=request_data,
                response_json=response_data
            )
        except Exception as e:
            logger.error(f"Error al registrar interacción: {str(e)}")


class AssistantConfigSaveView(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            phone_number = data.get("phone_number")
            config = data.get("config", {})
            user = WhatsAppUser.objects.get(phone_number=phone_number)
            assistant_config, _ = AssistantConfig.objects.get_or_create(user=user)
            assistant_config.assistant_name = config.get("assistant_name", assistant_config.assistant_name)
            assistant_config.language_style = config.get("language_style", assistant_config.language_style)
            assistant_config.experience_level = config.get("experience_level", assistant_config.experience_level)
            assistant_config.prediction_types = config.get("prediction_types", assistant_config.prediction_types)
            assistant_config.custom_settings = config.get("custom_settings", assistant_config.custom_settings)
            assistant_config.save()
            return JsonResponse({"status": "success"})
        except WhatsAppUser.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Usuario no encontrado"}, status=404)
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)


def verify_signature(request):
    """
    Verifica la firma de las solicitudes de WhatsApp usando HMAC.
    
    Args:
        request: La solicitud HTTP
        
    Returns:
        bool: True si la firma es válida, False en caso contrario
    """
    try:
        # Obtener la firma del encabezado
        signature = request.headers.get('X-Hub-Signature-256', '')
        
        if not signature.startswith('sha256='):
            return False
            
        # Extraer el hash
        signature = signature.replace('sha256=', '')
        
        # Cargar la clave privada
        with open(settings.WHATSAPP_PRIVATE_KEY_PATH, 'rb') as f:
            private_key = f.read()
            
        # Calcular el HMAC-SHA256 con la clave privada
        mac = hmac.new(
            private_key, 
            msg=request.body, 
            digestmod=hashlib.sha256
        )
        
        # Comparar las firmas
        expected_signature = mac.hexdigest()
        return hmac.compare_digest(signature, expected_signature)
    except Exception as e:
        logger.error(f"Error verifying signature: {e}")
        return False
