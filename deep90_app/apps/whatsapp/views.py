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
from .models import WhatsAppUser, Conversation, Message, WhatsAppUserStatus, UserInput
from .tasks import process_whatsapp_message, process_assistant_response
from ..sports_data.models import LiveFixtureData
from .flows import FootballDataFlow

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
