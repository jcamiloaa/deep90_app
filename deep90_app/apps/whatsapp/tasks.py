import logging
import time
from datetime import datetime, timedelta
from celery import shared_task
from django.db import transaction
from django.conf import settings
from django.utils import timezone
from .services import WhatsAppService
from .assistant_manager import AssistantManager
from .models import WhatsAppUser, Conversation, Message, WhatsAppUserStatus, SubscriptionPlan
from .sports_service import FootballDataService

logger = logging.getLogger(__name__)


@shared_task
def process_whatsapp_message(contact_data, message_data):
    """Process incoming WhatsApp messages."""
    try:
        wa_id = contact_data.get('wa_id')
        profile_name = contact_data.get('profile', {}).get('name', '')
        message_type = message_data.get('type')
        message_id = message_data.get('id')
        
        # Get or create WhatsApp user
        whatsapp_user, created = WhatsAppUser.objects.get_or_create(
            phone_number=wa_id,
            defaults={
                'profile_name': profile_name,
                'status': WhatsAppUserStatus.NEW
            }
        )
        
        # Initialize services
        whatsapp_service = WhatsAppService()
        assistant_manager = AssistantManager()
        
        # If this is a new user, send welcome message
        if created:
            welcome_message = (
                f"👋 ¡Hola {profile_name or 'amigo del fútbol'}!\n\n"
                "Bienvenido a Deep90, tu asistente de fútbol con IA.\n\n"
                "🔍 *¿Listo para dominar el fútbol con datos?*\n"
                "Deep90 lleva el poder del análisis a tu chat - Simple, revolucionario y 100% enfocado en ti.\n"
                "¡Únete a la nueva era del fútbol!\n\n"                
            )
            whatsapp_service.send_text_message(wa_id, welcome_message)
            # # Small delay to ensure message delivery
            # time.sleep(1)
            # # Show the main menu to new users
            # whatsapp_service.display_main_menu(wa_id)
            # # Additional delay
            # time.sleep(1)
        
        # Check if user is blacklisted
        if whatsapp_user.is_blacklisted:
            # Get support URL from settings
            support_url = getattr(settings, 'URL_SUPPORT', "https://www.deep90.com")
            
            logger.info(f"User {wa_id} is blacklisted. Message not processed.")
            whatsapp_service.send_text_message(
                wa_id,
                "Lo sentimos, tu cuenta está actualmente suspendida. Para más información, contacta con soporte en: "
                f"{support_url}"
            )
            return
            
        # Check if FREE user has exceeded daily message limit
        if whatsapp_user.subscription_plan == SubscriptionPlan.FREE:
            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_messages_count = Message.objects.filter(
                conversation__user=whatsapp_user,
                is_from_user=True,
                created_at__gte=today_start
            ).count()
            
            logger.info(f"########  ######    ######   User {wa_id} has sent {today_messages_count} messages today.")

            if today_messages_count >= settings.DAILY_MESSAGES_LIMIT:
                # Get URL from settings
                pricing_url = getattr(settings, 'URL_PLANS', "https://www.deep90.com/#pricing")
                
                # Notify user about the limit and send pricing URL
                logger.info(f"FREE user {wa_id} has exceeded daily message limit")
                whatsapp_service.send_text_message(
                    wa_id,
                    f"Has alcanzado el límite de  {settings.DAILY_MESSAGES_LIMIT} mensajes diarios para cuentas gratuitas. "
                    "Para continuar usando el asistente sin límites, actualiza a un plan Premium o Pro.\n\n"
                    f"Conoce nuestros planes de suscripción en: {pricing_url}"
                )
                return
                
        # Update user's last activity
        whatsapp_user.update_last_activity()
        
        # Process message based on type
        if message_type == 'text':
            text_body = message_data.get('text', {}).get('body', '')
            process_text_message(whatsapp_user, message_id, text_body)
        elif message_type == 'interactive':
            interactive_data = message_data.get('interactive', {})
            interactive_type = interactive_data.get('type')
            
            if interactive_type == 'button_reply':
                button_id = interactive_data.get('button_reply', {}).get('id')
                # Convert button reply to text message for processing
                button_text = f"button:{button_id}"
                process_text_message(whatsapp_user, message_id, button_text)
            elif interactive_type == 'list_reply':
                list_id = interactive_data.get('list_reply', {}).get('id')
                # Convert list reply to text message for processing
                list_text = f"list:{list_id}"
                process_text_message(whatsapp_user, message_id, list_text)
            else:
                logger.warning(f"Unhandled interactive type: {interactive_type}")
                whatsapp_service.send_text_message(
                    wa_id, 
                    "Lo siento, no puedo procesar este tipo de mensaje interactivo. Por favor escribe tu consulta en texto."
                )
        elif message_type == 'location':
            location_data = message_data.get('location', {})
            latitude = location_data.get('latitude')
            longitude = location_data.get('longitude')
            # Convert location to text message for the assistant
            location_text = f"location:{latitude},{longitude}"
            process_text_message(whatsapp_user, message_id, location_text)
        else:
            # For unhandled message types
            whatsapp_service.send_text_message(
                whatsapp_user.phone_number, 
                "Lo siento, no puedo procesar este tipo de mensaje. Por favor envíame tu consulta en formato texto."
            )
    
    except Exception as e:
        logger.error(f"Error processing WhatsApp message: {e}")
        raise


def process_text_message(whatsapp_user, message_id, text):
    """Process text messages from WhatsApp users by sending them to the assistant."""
    whatsapp_service = WhatsAppService()
    assistant_manager = AssistantManager()
    
    try:
        # Check if this is a special command for menu
        if text.lower() in ['menu', 'menú']:
            whatsapp_service.display_main_menu(whatsapp_user.phone_number)
            return
        
        # Check if this is from a list or button selection
        if text.startswith('list:'):
            list_id = text.replace('list:', '')
            process_list_reply(whatsapp_user, message_id, list_id)
            return
            
        if text.startswith('button:'):
            button_id = text.replace('button:', '')
            process_button_reply(whatsapp_user, message_id, button_id)
            return
            
        # Check if user is trying to exit assistant mode
        if is_in_assistant_mode(whatsapp_user) and text.lower() in ['exit', 'salir', 'fin', 'terminar']:
            end_assistant_conversation(whatsapp_user)
            return
            
        # If not in assistant mode, any text message should show the menu
        if not is_in_assistant_mode(whatsapp_user):
            # whatsapp_service.send_text_message(
            #     whatsapp_user.phone_number,
            #     "📱 Explora nuestras opciones en el menú principal:"
            # )
            # time.sleep(0.5)
            whatsapp_service.display_main_menu(whatsapp_user.phone_number)
            return
        
        # Here we know the user is in assistant mode, so we process the message
            
        # Check if FREE user has exceeded daily message limit
        if whatsapp_user.subscription_plan == SubscriptionPlan.FREE:
            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_messages_count = Message.objects.filter(
                conversation__user=whatsapp_user,
                is_from_user=True,
                created_at__gte=today_start
            ).count()
            
            # Hard limit on daily messages for free users
            if today_messages_count >= settings.DAILY_MESSAGES_LIMIT:
                # Get URL from settings
                pricing_url = getattr(settings, 'URL_PLANS', "https://www.deep90.com/#pricing")
                
                # Notify user about the limit and send pricing URL
                logger.info(f"FREE user {whatsapp_user.phone_number} has exceeded daily message limit")
                whatsapp_service.send_text_message(
                    whatsapp_user.phone_number,
                    f"Has alcanzado el límite de {settings.DAILY_MESSAGES_LIMIT} mensajes diarios para cuentas gratuitas. "
                    "Para continuar usando el asistente sin límites, actualiza a un plan Premium o Pro.\n\n"
                    f"Conoce nuestros planes de suscripción en: {pricing_url}"
                )
                return
        
        # Try to get an active conversation or the most recent inactive one
        conversation = Conversation.objects.filter(
            user=whatsapp_user,
            is_active=True
        ).first()
        
        # If no active conversation, check for a preserved one for premium users
        if not conversation and whatsapp_user.subscription_plan != SubscriptionPlan.FREE:
            conversation = Conversation.objects.filter(
                user=whatsapp_user,
                preserve_context=True
            ).order_by('-id').first()
            
            if conversation:
                # Validate that the thread still exists in OpenAI
                try:
                    messages = assistant_manager.get_assistant_messages(conversation.thread_id)
                    thread_exists = len(messages) > 0
                    if thread_exists:
                        # Reactivate the conversation
                        conversation.is_active = True
                        conversation.save()
                        logger.info(f"Reactivated existing conversation for {whatsapp_user.phone_number}")
                    else:
                        conversation = None
                except Exception as e:
                    logger.error(f"Error validating thread: {e}")
                    conversation = None
        
        # If still no valid conversation, create a new one
        if not conversation:
            # Create a new thread
            thread_id = assistant_manager.create_thread()
            
            # Create conversation record
            conversation = Conversation.objects.create(
                user=whatsapp_user,
                thread_id=thread_id,
                is_active=True,
                # Premium users' conversations are preserved for context
                preserve_context=(whatsapp_user.subscription_plan != SubscriptionPlan.FREE)
            )
            
            # Add initial system context message
            user_info = {
                'name': whatsapp_user.full_name or whatsapp_user.profile_name or 'Usuario',
                'subscription': whatsapp_user.subscription_plan,
            }
            
            assistant_manager.add_message_to_thread(
                thread_id,
                f"Nuevo usuario con suscripción {user_info['subscription']}. " +
                f"Su nombre es {user_info['name']}. " +
                "Preséntate como un asistente experto en fútbol de Deep90.",
                user_info
            )
            
        with transaction.atomic():
            # Save user message to database
            Message.objects.create(
                conversation=conversation,
                message_id=message_id,
                is_from_user=True,
                content=text,
                message_type='text'
            )
            
            # Update conversation last message time
            conversation.update_last_message_time()
            
            # Add message to OpenAI thread
            user_info = {
                'name': whatsapp_user.full_name or whatsapp_user.profile_name or 'Usuario',
                'subscription': whatsapp_user.subscription_plan,
            }
            
            assistant_manager.add_message_to_thread(conversation.thread_id, text, user_info)
            
            # Run the assistant with appropriate model based on subscription
            assistant_id = assistant_manager.get_assistant_for_user(whatsapp_user)
            run_id = assistant_manager.run_assistant(conversation.thread_id, assistant_id)
            
            # Send typing indicator message
            whatsapp_service.send_text_message(
                whatsapp_user.phone_number,
                "⏳ Procesando..."
            )
            
            # Queue task to check run completion
            process_assistant_run.delay(
                whatsapp_user.phone_number,
                conversation.id,
                conversation.thread_id,
                run_id
            )
    
    except Exception as e:
        logger.error(f"Error processing text message: {e}")
        whatsapp_service.send_text_message(
            whatsapp_user.phone_number,
            "Lo siento, ha ocurrido un error al procesar tu mensaje. Por favor intenta nuevamente."
        )
        raise


def is_in_assistant_mode(whatsapp_user):
    """Check if user is currently in an active assistant conversation."""
    return Conversation.objects.filter(user=whatsapp_user, is_active=True).exists()


def process_button_reply(whatsapp_user, message_id, button_id):
    """Process button replies from WhatsApp users."""
    whatsapp_service = WhatsAppService()
    
    # Handle different button options
    if button_id == 'start_assistant':
        start_assistant_conversation(whatsapp_user)
    elif button_id == 'exit_assistant':
        end_assistant_conversation(whatsapp_user)
    elif button_id == 'subscribe_premium':
        process_subscription_change(whatsapp_user, SubscriptionPlan.PREMIUM)
    elif button_id == 'subscribe_pro':
        process_subscription_change(whatsapp_user, SubscriptionPlan.PRO)
    else:
        whatsapp_service.send_text_message(
            whatsapp_user.phone_number, 
            "Opción no reconocida. Por favor selecciona una opción válida."
        )
        time.sleep(1)
        whatsapp_service.display_main_menu(whatsapp_user.phone_number)


def process_list_reply(whatsapp_user, message_id, list_id):
    """Process list replies from WhatsApp users when selecting from the main menu."""
    whatsapp_service = WhatsAppService()
    
    # Handle different list options
    if list_id == 'assistant':
        # Iniciar conversación con el asistente
        start_assistant_conversation(whatsapp_user)
    elif list_id == 'profile':
        # Mostrar información de perfil o iniciar flujo de registro
        if whatsapp_user.status == WhatsAppUserStatus.NEW:
            whatsapp_service.send_text_message(
                whatsapp_user.phone_number,
                "Para personalizar tu experiencia en Deep90, completa tu perfil a continuación:"
            )
            time.sleep(1)
            whatsapp_service.send_registration_flow(whatsapp_user.phone_number)
        else:
            show_profile(whatsapp_user)
    elif list_id == 'results':
        # Mostrar resultados en vivo
        show_results(whatsapp_user)
    elif list_id == 'fixtures':
        # Mostrar próximos partidos
        show_fixtures(whatsapp_user)
    elif list_id == 'subscription':
        # Mostrar opciones de suscripción
        show_subscription_options(whatsapp_user)
    elif list_id == 'help':
        # Mostrar ayuda
        show_help(whatsapp_user)
    else:
        whatsapp_service.send_text_message(
            whatsapp_user.phone_number, 
            "Opción no reconocida. Por favor selecciona una opción válida."
        )
        time.sleep(1)
        whatsapp_service.display_main_menu(whatsapp_user.phone_number)


def process_location(whatsapp_user, message_id, location_data):
    """Process location data from WhatsApp users."""
    whatsapp_service = WhatsAppService()
    latitude = location_data.get('latitude')
    longitude = location_data.get('longitude')
    
    # Send acknowledgment and menu
    whatsapp_service.send_text_message(
        whatsapp_user.phone_number, 
        f"He recibido tu ubicación (Lat: {latitude}, Long: {longitude}). Esta función estará disponible próximamente."
    )
    time.sleep(1)
    whatsapp_service.display_main_menu(whatsapp_user.phone_number)


def start_assistant_conversation(whatsapp_user):
    """Start a conversation with the OpenAI Assistant."""
    whatsapp_service = WhatsAppService()
    assistant_manager = AssistantManager()
    
    try:
        # Desactivar cualquier conversación activa existente
        Conversation.objects.filter(user=whatsapp_user, is_active=True).update(is_active=False)
        
        # Para usuarios premium/pro, intentar restaurar una conversación previa con contexto preservado
        preserved_conversation = None
        thread_exists = False
        if whatsapp_user.subscription_plan != SubscriptionPlan.FREE:
            preserved_conversation = Conversation.objects.filter(
                user=whatsapp_user, 
                is_active=False, 
                preserve_context=True
            ).order_by('-id').first()
            
            if preserved_conversation:
                # Verificar que el thread aún existe en OpenAI
                try:
                    # Intenta obtener mensajes del thread para verificar que existe
                    messages = assistant_manager.get_assistant_messages(preserved_conversation.thread_id)
                    thread_exists = len(messages) > 0
                    logger.info(f"Thread {preserved_conversation.thread_id} existe: {thread_exists}")
                except Exception as e:
                    logger.error(f"Error verificando thread: {e}")
                    thread_exists = False
                    
                if thread_exists:
                    logger.info(f"Usuario {whatsapp_user.subscription_plan} {whatsapp_user.phone_number}: Restaurando conversación previa con ID {preserved_conversation.id}")
                else:
                    logger.warning(f"Thread {preserved_conversation.thread_id} no existe o es inválido. Creando uno nuevo.")
                    preserved_conversation = None
        
        # Si encontramos una conversación preservada válida para usuarios premium/pro, reactivarla
        if preserved_conversation and thread_exists:
            preserved_conversation.is_active = True
            preserved_conversation.save()
            conversation = preserved_conversation
            
            # Mensaje de bienvenida de regreso
            # whatsapp_service.send_text_message(
            #     whatsapp_user.phone_number,
            #     "🤖 *Modo Asistente Activado* 🤖\n\n"
            #     "¡Hola de nuevo! He recuperado nuestra conversación anterior.\n"
            #     "¿En qué puedo ayudarte ahora?\n\n"
            #     "Para salir, escribe 'salir' o 'exit'."
            # )
            
            try:
                # Añadir mensaje al thread explicando el regreso
                user_info = {
                    'name': whatsapp_user.full_name or whatsapp_user.profile_name or 'Usuario',
                    'subscription': whatsapp_user.subscription_plan,
                }
                
                assistant_manager.add_message_to_thread(
                    preserved_conversation.thread_id,
                    "El usuario ha regresado a la conversación. Es un usuario con suscripción " +
                    f"{user_info['subscription']}. Mantén el contexto de las conversaciones anteriores.",
                    user_info
                )
                
                # Ejecutar el asistente con el modelo apropiado según la suscripción
                assistant_id = assistant_manager.get_assistant_for_user(whatsapp_user)
                run_id = assistant_manager.run_assistant(preserved_conversation.thread_id, assistant_id)
                
                # Encolar tarea para verificar la finalización de la ejecución
                process_assistant_run.delay(
                    whatsapp_user.phone_number,
                    preserved_conversation.id,
                    preserved_conversation.thread_id,
                    run_id
                )
            except Exception as e:
                logger.error(f"Error al reactivar thread existente: {e}")
                # Si falla, creamos una nueva conversación en lugar de mostrar error
                preserved_conversation.is_active = False
                preserved_conversation.save()
                create_new_conversation(whatsapp_user, assistant_manager, whatsapp_service)
        else:
            # No hay conversación preservada válida o es usuario FREE, crear una nueva
            create_new_conversation(whatsapp_user, assistant_manager, whatsapp_service)
        
    except Exception as e:
        logger.error(f"Error starting assistant conversation: {e}")
        whatsapp_service.send_text_message(
            whatsapp_user.phone_number,
            "Lo siento, hubo un error al iniciar la conversación con el asistente. Por favor intenta nuevamente más tarde."
        )
        time.sleep(1)
        whatsapp_service.display_main_menu(whatsapp_user.phone_number)


def create_new_conversation(whatsapp_user, assistant_manager, whatsapp_service):
    """Helper function to create a new conversation with the assistant."""
    try:
        # Crear un nuevo thread para la conversación
        thread_id = assistant_manager.create_thread()
        
        # Crear un nuevo registro de conversación
        conversation = Conversation.objects.create(
            user=whatsapp_user,
            thread_id=thread_id,
            is_active=True,
            # Establecer preserve_context según el plan
            preserve_context=(whatsapp_user.subscription_plan != SubscriptionPlan.FREE)
        )
        
        # Enviar mensaje de bienvenida para el modo asistente
        whatsapp_service.send_text_message(
            whatsapp_user.phone_number,
            "🤖 *Modo Asistente Activado* 🤖\n\n"
            "Ahora estás hablando con nuestro asistente de fútbol con IA.\n"
            "¡Pregúntame lo que quieras sobre fútbol!\n"
            "Para salir, escribe 'salir' o 'exit'."
        )
        
        # Añadir mensaje inicial al thread
        user_info = {
            'name': whatsapp_user.full_name or whatsapp_user.profile_name or 'Usuario',
            'subscription': whatsapp_user.subscription_plan,
        }
        
        assistant_manager.add_message_to_thread(
            thread_id,
            "El usuario acaba de activar el modo asistente en WhatsApp. " +
            f"Su nombre es {user_info['name']} y tiene una suscripción {user_info['subscription']}. " +
            "Salúdalo como un asistente experto en fútbol y preséntate. " +
            "Ofrece tu ayuda para responder preguntas sobre fútbol, como resultados, próximos partidos, " +
            "clasificaciones, estadísticas de equipos o jugadores, etc.",
            user_info
        )
        
        # Ejecutar el asistente con el modelo apropiado según la suscripción
        assistant_id = assistant_manager.get_assistant_for_user(whatsapp_user)
        run_id = assistant_manager.run_assistant(thread_id, assistant_id)
        
        # Encolar tarea para verificar la finalización de la ejecución
        process_assistant_run.delay(
            whatsapp_user.phone_number,
            conversation.id,
            thread_id,
            run_id
        )
        return conversation
    except Exception as e:
        logger.error(f"Error creating new conversation: {e}")
        raise


def end_assistant_conversation(whatsapp_user):
    """End a conversation with the OpenAI Assistant."""
    whatsapp_service = WhatsAppService()
    
    # Para usuarios con suscripción FREE, cerrar completamente la conversación
    # Para usuarios PREMIUM y PRO, solo marcar como inactiva pero mantener el thread para contexto
    if whatsapp_user.subscription_plan == SubscriptionPlan.FREE:
        # End any active conversations completely for FREE users
        Conversation.objects.filter(user=whatsapp_user, is_active=True).update(
            is_active=False, 
            preserve_context=False
        )
        logger.info(f"Usuario FREE {whatsapp_user.phone_number}: Conversación cerrada completamente")
    else:
        # For paid users, just mark the conversation as inactive but keep the thread
        Conversation.objects.filter(user=whatsapp_user, is_active=True).update(
            is_active=False, 
            preserve_context=True
        )
        logger.info(f"Usuario Premium {whatsapp_user.phone_number}: Conversación preservada para contexto futuro")
    
    # Send exit message
    whatsapp_service.send_text_message(
        whatsapp_user.phone_number,
        "Has salido del modo asistente."
    )
    time.sleep(1)
    whatsapp_service.display_main_menu(whatsapp_user.phone_number)


def show_fixtures(whatsapp_user):
    """Show upcoming fixtures to the user."""
    whatsapp_service = WhatsAppService()
    
    # Use the FootballDataService to get real data
    service = FootballDataService()
    fixtures = service.get_upcoming_fixtures(days=7, limit=5)
    message = service.format_fixtures_message(fixtures)
    
    whatsapp_service.send_text_message(whatsapp_user.phone_number, message)
    time.sleep(1)
    whatsapp_service.display_main_menu(whatsapp_user.phone_number)


def show_results(whatsapp_user):
    """Show live match results to the user."""
    whatsapp_service = WhatsAppService()
    
    # Instead of sending formatted text message with live matches,
    # we now send the interactive flow for live results
    whatsapp_service.send_live_results_flow(whatsapp_user.phone_number)
    
    # No need to display the main menu right after, as the flow
    # will provide navigation options to return to the menu


def show_profile(whatsapp_user):
    """Show user's profile information."""
    whatsapp_service = WhatsAppService()
    
    subscription = "Gratuito"
    if whatsapp_user.subscription_plan == SubscriptionPlan.PREMIUM:
        subscription = "Premium"
    elif whatsapp_user.subscription_plan == SubscriptionPlan.PRO:
        subscription = "Profesional"
    
    subscription_expiry = ""
    if whatsapp_user.subscription_expiry:
        expiry_date = whatsapp_user.subscription_expiry.strftime('%d/%m/%Y')
        subscription_expiry = f"Expira: {expiry_date}"
    
    profile_message = (
        "👤 *Tu Perfil* 👤\n\n"
        f"Nombre: {whatsapp_user.full_name or whatsapp_user.profile_name or 'No establecido'}\n"
        f"Teléfono: {whatsapp_user.phone_number}\n"
        f"Email: {whatsapp_user.email or 'No establecido'}\n"
        f"Plan: {subscription}\n"
        f"{subscription_expiry}\n\n"
        "Para actualizar tu información, por favor completa el formulario de registro."
    )
    
    whatsapp_service.send_text_message(whatsapp_user.phone_number, profile_message)
    time.sleep(1)
    whatsapp_service.display_main_menu(whatsapp_user.phone_number)


def show_subscription_options(whatsapp_user):
    """Show subscription options to the user."""
    whatsapp_service = WhatsAppService()
    
    subscription_message = (
        "💳 *Opciones de Suscripción* 💳\n\n"
        "• Plan Gratuito: Acceso básico al asistente\n"
        "• Plan Premium: $9.99/mes - Análisis avanzados y predicciones\n"
        "• Plan Profesional: $19.99/mes - Todos los beneficios y datos exclusivos\n\n"
        "Para actualizar tu plan, selecciona una opción:"
    )
    
    buttons = [
        {
            "type": "reply",
            "reply": {
                "id": "subscribe_premium",
                "title": "Premium"
            }
        },
        {
            "type": "reply",
            "reply": {
                "id": "subscribe_pro",
                "title": "Profesional"
            }
        }
    ]
    
    whatsapp_service.send_button_template(
        whatsapp_user.phone_number, 
        subscription_message, 
        buttons
    )


def process_subscription_change(whatsapp_user, new_plan):
    """Process a subscription change request."""
    whatsapp_service = WhatsAppService()
    old_plan = whatsapp_user.subscription_plan
    
    # Simple mock implementation - in a real scenario, you would process payment, etc.
    whatsapp_user.subscription_plan = new_plan
    whatsapp_user.subscription_expiry = datetime.now().replace(year=datetime.now().year + 1)
    whatsapp_user.save()
    
    # Notify user of the change
    plan_name = "Premium" if new_plan == SubscriptionPlan.PREMIUM else "Profesional"
    expiry_date = whatsapp_user.subscription_expiry.strftime('%d/%m/%Y')
    
    whatsapp_service.send_text_message(
        whatsapp_user.phone_number,
        f"🎉 ¡Felicidades! Tu suscripción ha sido actualizada al plan {plan_name}.\n\n"
        f"Tu suscripción está activa hasta el {expiry_date}.\n\n"
        "Ahora tienes acceso a todas las funciones premium de nuestro asistente."
    )
    
    time.sleep(1)
    whatsapp_service.display_main_menu(whatsapp_user.phone_number)


def show_help(whatsapp_user):
    """Show help information to the user."""
    whatsapp_service = WhatsAppService()
    
    help_message = (
        "❓ *Ayuda* ❓\n\n"
        "• Para ver el menú principal: Escribe 'menu'\n"
        "• Para hablar con el asistente: Selecciona 'Hablar con asistente' en el menú\n"
        "• Para salir del asistente: Escribe 'salir' o 'exit'\n"
        "• Para ver tu perfil: Selecciona 'Mi Perfil' en el menú\n\n"
        "Si tienes problemas técnicos, contacta al soporte: support@deep90.com"
    )
    
    whatsapp_service.send_text_message(whatsapp_user.phone_number, help_message)
    time.sleep(1)
    whatsapp_service.display_main_menu(whatsapp_user.phone_number)


@shared_task
def process_assistant_run(user_phone, conversation_id, thread_id, run_id):
    """Process an assistant run and send the response when complete."""
    try:
        whatsapp_user = WhatsAppUser.objects.get(phone_number=user_phone)
        conversation = Conversation.objects.get(id=conversation_id)
        whatsapp_service = WhatsAppService()
        assistant_manager = AssistantManager()
        
        # Check run status
        run = assistant_manager.check_run_status(thread_id, run_id)
        status = run.status
        
        if status == 'completed':
            # Get the latest messages from the assistant
            messages = assistant_manager.get_assistant_messages(thread_id)
            
            if messages:
                # Get the most recent message
                latest_message = messages[0]
                message_content = latest_message['content']
                
                # Save message to database
                Message.objects.create(
                    conversation=conversation,
                    is_from_user=False,
                    content=message_content,
                    message_type='text'
                )
                
                # Define buttons for continuing or exiting
                buttons = [
                    {
                        "type": "reply",
                        "reply": {
                            "id": "exit_assistant",
                            "title": "Volver al menú"
                        }
                    }
                ]
                
                # Send the assistant's response with buttons in one message
                whatsapp_service.send_button_template(
                    whatsapp_user.phone_number,
                    message_content,
                    buttons
                )
                
                logger.info(f"Respuesta del asistente enviada a {whatsapp_user.phone_number}: {message_content[:50]}...")
            else:
                # No se encontraron mensajes del asistente
                # Add button to return to main menu
                buttons = [
                    {
                        "type": "reply",
                        "reply": {
                            "id": "exit_assistant",
                            "title": "Volver al menú"
                        }
                    }
                ]
                
                whatsapp_service.send_button_template(
                    whatsapp_user.phone_number,
                    "Lo siento, parece que el asistente no ha podido generar una respuesta. Por favor intenta nuevamente.",
                    buttons
                )
                logger.warning(f"No se encontraron mensajes del asistente para el thread {thread_id}")
        
        elif status == 'requires_action':
            # Assistant is requesting action through tools
            logger.info(f"Run requires action: {run.required_action}")
            
            # Process tool calls
            updated_run = assistant_manager.process_tool_calls(
                thread_id, 
                run_id,
                run.required_action
            )
            
            # Re-check status after tool execution
            process_assistant_run.delay(user_phone, conversation_id, thread_id, updated_run.id)
            
        elif status in ['failed', 'cancelled', 'expired']:
            # Run failed
            # Add button to return to main menu
            buttons = [
                {
                    "type": "reply",
                    "reply": {
                        "id": "exit_assistant",
                        "title": "Volver al menú"
                    }
                }
            ]
            
            whatsapp_service.send_button_template(
                whatsapp_user.phone_number,
                "Lo siento, hubo un problema al procesar tu mensaje. Por favor intenta nuevamente.",
                buttons
            )
            logger.error(f"Run falló con estado: {status} para el thread {thread_id}")
        
        elif status in ['queued', 'in_progress']:
            # Still processing, check again in a few seconds
            process_assistant_run.apply_async(
                args=[user_phone, conversation_id, thread_id, run_id],
                countdown=3  # Check again in 3 seconds
            )
        
    except Exception as e:
        logger.error(f"Error processing assistant run: {e}")
        
        # Try to notify user of the error
        try:
            whatsapp_user = WhatsAppUser.objects.get(phone_number=user_phone)
            whatsapp_service = WhatsAppService()
            
            # Add button to return to main menu
            buttons = [
                {
                    "type": "reply",
                    "reply": {
                        "id": "exit_assistant",
                        "title": "Volver al menú"
                    }
                }
            ]
            
            whatsapp_service.send_button_template(
                whatsapp_user.phone_number,
                "Lo siento, ocurrió un error al procesar tu solicitud. Por favor intenta nuevamente.",
                buttons
            )
        except Exception:
            logger.error("Could not notify user of error")


@shared_task
def process_assistant_response(thread_id, run_id):
    """Process response from Assistant API after completion via webhook."""
    try:
        # Find the conversation with this thread_id
        conversation = Conversation.objects.filter(thread_id=thread_id, is_active=True).first()
        
        if conversation:
            whatsapp_user = conversation.user
            
            # Process the completed run
            process_assistant_run.delay(
                whatsapp_user.phone_number,  # Cambiado de whatsapp_user.id a phone_number
                conversation.id,
                thread_id,
                run_id
            )
    
    except Exception as e:
        logger.error(f"Error processing assistant response: {e}")
        raise