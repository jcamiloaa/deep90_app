import json
import logging
import requests
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from django.conf import settings
from openai import OpenAI
from .models import WhatsAppUser, Conversation, Message, SubscriptionPlan, WhatsAppUserStatus
from .assistant_manager import AssistantManager

logger = logging.getLogger(__name__)

class WhatsAppService:
    """Service to handle WhatsApp Business API communications."""
    
    def __init__(self):
        """Initialize WhatsApp service with credentials from settings."""
        self.verify_token = settings.WHATSAPP_VERIFY_TOKEN
        self.access_token = settings.WHATSAPP_ACCESS_TOKEN
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.version = settings.WHATSAPP_VERSION_API
        self.flow_sign_up = settings.WHATSAPP_FLOW_SIGN_UP 
        self.flow_sign_up_screem = settings.WHATSAPP_FLOW_SIGN_UP_SCREEM
        self.flow_live_result = settings.WHATSAPP_FLOW_LIVE_RESULT
        self.flow_live_result_screen = settings.WHATSAPP_FLOW_LIVE_RESULT_SCREEM
        self.flow_live_result_token = settings.WHATSAPP_FLOW_LIVE_RESULT_TOKEN

        self.flow_mode = settings.WHATSAPP_FLOW_MODE
        self.flow_version_messages = settings.WHATSAPP_FLOW_VERSION_MESSAGES

        
        # API endpoints
        self.base_url = f"https://graph.facebook.com/{self.version}"
        self.send_message_url = f"{self.base_url}/{self.phone_number_id}/messages"

    def log_message(self, phone_number, content, message_type='text', is_from_user=False, message_id=None, request_json=None, response_json=None):
        """
        Log a message to the database for record-keeping.
        
        Args:
            phone_number: The WhatsApp phone number
            content: The content of the message
            message_type: The type of the message (text, button, list, flow, etc)
            is_from_user: Whether the message is from the user (False for outgoing messages)
            message_id: Optional message ID for tracking
            request_json: Complete JSON of the request (webhook or API call)
            response_json: Complete JSON of the response
            
        Returns:
            The created Message object or None if creation failed
        """
        try:
            # Get the user
            whatsapp_user = WhatsAppUser.objects.get(phone_number=phone_number)
            
            # Get or create a conversation for system messages if needed
            conversation, created = Conversation.objects.get_or_create(
                user=whatsapp_user,
                defaults={
                    'thread_id': f"system_conversation_{phone_number}",
                    'is_active': False
                },
                thread_id__startswith="system_conversation_"
            )
            
            # Create the message record
            message = Message.objects.create(
                conversation=conversation,
                message_id=message_id,
                is_from_user=is_from_user,
                content=content,
                message_type=message_type,
                request_json=request_json,
                response_json=response_json
            )
            
            logger.debug(f"Message logged: {message}")
            return message
            
        except WhatsAppUser.DoesNotExist:
            logger.warning(f"Attempted to log message for nonexistent user: {phone_number}")
            return None
        except Exception as e:
            logger.error(f"Failed to log message: {e}")
            return None
    
    def verify_webhook(self, mode, token, challenge):
        """
        Verify webhook subscription on Meta/WhatsApp side.
        
        Args:
            mode: hub.mode parameter from GET request
            token: hub.verify_token parameter from GET request
            challenge: hub.challenge parameter from GET request
            
        Returns:
            Challenge string if verification succeeds, None otherwise
        """
        # Check if mode and token were sent
        if mode and token:
            # Check the mode and token sent are correct
            if mode == 'subscribe' and token == self.verify_token:
                # Respond with the challenge token from the request
                logger.info("WEBHOOK_VERIFIED")
                return challenge
            else:
                # Responds with '403 Forbidden' if verify tokens do not match
                logger.warning("WEBHOOK_TOKEN_MISMATCH")
                return None
        else:
            logger.warning("WEBHOOK_MISSING_PARAMS")
            return None
    
    def send_text_message(self, to, text):
        """
        Send a text message to a WhatsApp user.
        
        Args:
            to: Recipient phone number
            text: Message text
            
        Returns:
            API response
        """
        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.access_token}'
            }
            
            data = {
                'messaging_product': 'whatsapp',
                'recipient_type': 'individual',
                'to': to,
                'type': 'text',
                'text': {
                    'preview_url': True,
                    'body': text
                }
            }
            
            response = requests.post(
                self.send_message_url, 
                headers=headers, 
                json=data
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to send text message: {response.text}")
            else:
                # Log the sent message to the database
                try:
                    message_id = response.json().get('messages', [{}])[0].get('id', None)
                    self.log_message(to, text, 'text', False, message_id, request_json=data, response_json=response.json())
                except Exception as e:
                    logger.error(f"Error logging sent text message: {e}")
            
            return response
        
        except Exception as e:
            logger.error(f"Error sending text message: {e}")
            raise
    
    def send_template_message(self, to, template_name, language="es", components=None):
        """
        Send a template message to a WhatsApp user.
        
        Args:
            to: Recipient phone number
            template_name: Template name
            language: Language code
            components: Template components
            
        Returns:
            API response
        """
        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.access_token}'
            }
            
            data = {
                'messaging_product': 'whatsapp',
                'recipient_type': 'individual',
                'to': to,
                'type': 'template',
                'template': {
                    'name': template_name,
                    'language': {
                        'code': language
                    }
                }
            }
            
            if components:
                data['template']['components'] = components
            
            response = requests.post(
                self.send_message_url, 
                headers=headers, 
                json=data
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to send template: {response.text}")
            else:
                # Log the sent template message
                try:
                    message_id = response.json().get('messages', [{}])[0].get('id', None)
                    # Create a readable content for logging
                    content = f"Plantilla: {template_name} ({language})"
                    if components:
                        content += f"\nComponentes: {json.dumps(components, ensure_ascii=False)}"
                    self.log_message(to, content, 'template', False, message_id, request_json=data, response_json=response.json())
                except Exception as e:
                    logger.error(f"Error logging sent template message: {e}")
            
            return response
        
        except Exception as e:
            logger.error(f"Error sending template: {e}")
            raise
    
    def send_button_template(self, to, text, buttons):
        """
        Send an interactive button message to a WhatsApp user.
        
        Args:
            to: Recipient phone number
            text: Message text
            buttons: List of button objects
            
        Returns:
            API response
        """
        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.access_token}'
            }
            
            data = {
                'messaging_product': 'whatsapp',
                'recipient_type': 'individual',
                'to': to,
                'type': 'interactive',
                'interactive': {
                    'type': 'button',
                    'body': {
                        'text': text
                    },
                    'action': {
                        'buttons': buttons
                    }
                }
            }
            
            response = requests.post(
                self.send_message_url, 
                headers=headers, 
                json=data
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to send button template: {response.text}")
            else:
                # Log the sent button message
                try:
                    message_id = response.json().get('messages', [{}])[0].get('id', None)
                    # Create a readable content for logging
                    button_labels = ", ".join([btn.get('reply', {}).get('title', 'Unknown') for btn in buttons])
                    content = f"{text}\n\nBotones: [{button_labels}]"
                    self.log_message(to, content, 'button', False, message_id, request_json=data, response_json=response.json())
                except Exception as e:
                    logger.error(f"Error logging sent button message: {e}")
            
            return response
        
        except Exception as e:
            logger.error(f"Error sending button template: {e}")
            raise
    
    def send_list_template(self, to, text, button_text, sections):
        """
        Send an interactive list message to a WhatsApp user.
        
        Args:
            to: Recipient phone number
            text: Message text
            button_text: Text for the list button
            sections: List of section objects
            
        Returns:
            API response
        """
        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.access_token}'
            }
            
            data = {
                'messaging_product': 'whatsapp',
                'recipient_type': 'individual',
                'to': to,
                'type': 'interactive',
                'interactive': {
                    'type': 'list',
                    'header': {
                        'type': 'text',
                        'text': 'Deep90 ⚽'
                    },
                    'body': {
                        'text': text
                    },
                    'footer': {
                        'text': 'Deep90 - Tu asistente de fútbol'
                    },
                    'action': {
                        'button': button_text,
                        'sections': sections
                    }
                }
            }
            
            response = requests.post(
                self.send_message_url, 
                headers=headers, 
                json=data
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to send list template: {response.text}")
            else:
                # Log the sent list message
                try:
                    message_id = response.json().get('messages', [{}])[0].get('id', None)
                    # Create a readable content for logging
                    section_titles = [section.get('title', 'Unnamed Section') for section in sections]
                    content = f"{text}\n\nMenú: {button_text}\nSecciones: {', '.join(section_titles)}"
                    self.log_message(to, content, 'list', False, message_id, request_json=data, response_json=response.json())
                except Exception as e:
                    logger.error(f"Error logging sent list message: {e}")
            
            return response
        
        except Exception as e:
            logger.error(f"Error sending list template: {e}")
            raise
    
    def send_registration_flow(self, to):
        """
        Send the user registration flow.
        
        Args:
            to: Recipient phone number
            
        Returns:
            API response
        """
        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.access_token}'
            }
            
            data = {
                'messaging_product': 'whatsapp',
                'recipient_type': 'individual',
                'to': to,
                'type': 'interactive',
                'interactive': {
                    'type': 'flow',
                    'header': {
                        'type': 'text',
                        'text': 'Registro de Usuario'
                    },
                    'body': {
                        'text': '¡Completa tu perfil para personalizar tu experiencia en Deep90!'
                    },
                    'footer': {
                        'text': 'Los datos son solo para mejorar tu experiencia'
                    },
                    'action': {
                        'name': 'flow',
                        'parameters': {
                            'flow_message_version': self.flow_version_messages,
                            'flow_token': self.flow_sign_up,
                            'flow_id': self.flow_sign_up,
                            'flow_cta': 'Completar Registro',
                            'mode': self.flow_mode,  # Changed from flow_mode to mode
                            'flow_action': 'navigate',            
                            'flow_action_payload': {
                                'screen': self.flow_sign_up_screem,
                                'data': {                               
                                }
                            }
                        }
                    }
                }
            }
            
            response = requests.post(
                self.send_message_url, 
                headers=headers, 
                json=data
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to send registration flow: {response.text}")
            else:
                # Log the sent flow message
                try:
                    message_id = response.json().get('messages', [{}])[0].get('id', None)
                    content = "¡Completa tu perfil para personalizar tu experiencia en Deep90!"
                    self.log_message(to, content, 'flow_registration', False, message_id, request_json=data, response_json=response.json())
                except Exception as e:
                    logger.error(f"Error logging sent registration flow message: {e}")
            
            return response
        
        except Exception as e:
            logger.error(f"Error sending registration flow: {e}")
            raise
            
    def send_live_results_flow(self, to):
        """
        Send the live results flow to display matches currently being played.
        
        Args:
            to: Recipient phone number
            
        Returns:
            API response
        """
        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.access_token}'
            }
            
            data = {
                'messaging_product': 'whatsapp',
                'recipient_type': 'individual',
                'to': to,
                'type': 'interactive',
                'interactive': {
                    'type': 'flow',
                    'header': {
                        'type': 'text',
                        'text': 'Resultados en Vivo'
                    },
                    'body': {
                        'text': '¡Consulta los partidos que se están jugando ahora mismo!'
                    },
                    'footer': {
                        'text': 'Datos actualizados en tiempo real'
                    },
                    'action': {
                        'name': 'flow',
                        'parameters': {
                            'flow_message_version': self.flow_version_messages,
                            'flow_token': self.flow_live_result_token,
                            'flow_id': self.flow_live_result,
                            'flow_cta': 'Ver',
                            'mode': self.flow_mode,        
                            'flow_action_payload': {
                                'screen': self.flow_live_result_screen                            
                            }
                        }
                    }
                }
            }
            
            response = requests.post(
                self.send_message_url, 
                headers=headers, 
                json=data
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to send live results flow: {response.text}")
            else:
                # Log the sent flow message
                try:
                    message_id = response.json().get('messages', [{}])[0].get('id', None)
                    content = "¡Consulta los partidos que se están jugando ahora mismo!"
                    self.log_message(to, content, 'flow_live_results', False, message_id, request_json=data, response_json=response.json())
                except Exception as e:
                    logger.error(f"Error logging sent live results flow message: {e}")
            
            return response
        
        except Exception as e:
            logger.error(f"Error sending live results flow: {e}")
            raise
    
    def display_main_menu(self, to):
        """
        Display the main menu organized by sections.
        
        Args:
            to: Recipient phone number
            
        Returns:
            API response
        """
        sections = [
            {
                "title": "Mi Cuenta",
                "rows": [
                    {
                        "id": "profile",
                        "title": "Mi Perfil",
                        "description": "Ver y completar mi información personal"
                    },
                    {
                        "id": "subscription",
                        "title": "Mi Suscripción",
                        "description": "Gestionar o actualizar mi plan"
                    }
                ]
            },
            {
                "title": "Resultados y Partidos",
                "rows": [
                    {
                        "id": "results",
                        "title": "Resultados en vivo",
                        "description": "Consultar partidos que se están jugando ahora"
                    },
                    {
                        "id": "fixtures",
                        "title": "Próximos partidos",
                        "description": "Ver calendario de partidos"
                    }
                ]
            },
            {
                "title": "Asistente IA",
                "rows": [                   
                    {
                        "id": "help",
                        "title": "Ayuda y soporte",
                        "description": "Obtén información de uso y soporte"
                    }
                ]
            }
        ]


        #  {
        #                 "id": "assistant",
        #                 "title": "Hablar con asistente",
        #                 "description": "Conversa con nuestro asistente de fútbol"
        #             },
        
        return self.send_list_template(
            to=to,
            text="Explora nuestras opciones en el menú principal",
            button_text="Ver opciones",
            sections=sections
        )


class OpenAIAssistantService:
    """Service for OpenAI Assistant API operations."""
    
    def __init__(self):
        """Initialize OpenAI assistant service."""
        self.assistant_manager = AssistantManager()
    
    def create_thread(self):
        """Create a new conversation thread."""
        return self.assistant_manager.create_thread()
    
    def add_message_to_thread(self, thread_id, content, user_info=None):
        """Add a message to an existing thread."""
        return self.assistant_manager.add_message_to_thread(thread_id, content, user_info)
    
    def run_assistant(self, thread_id, assistant_id, tools_config=None):
        """Run the assistant on a given thread."""
        return self.assistant_manager.run_assistant(thread_id, assistant_id, tools_config)
    
    def check_run_status(self, thread_id, run_id):
        """Check the status of an assistant run."""
        run = self.assistant_manager.check_run_status(thread_id, run_id)
        return run.status
    
    def get_assistant_messages(self, thread_id, after_message_id=None):
        """Get assistant messages from a thread."""
        messages = self.assistant_manager.get_assistant_messages(thread_id, after_message_id)
        if messages:
            # Return just the content of messages for simplicity
            return [message.get('content', '') for message in messages]
        return []
    
    def get_assistant_id(self, subscription_plan):
        """Get the appropriate assistant ID based on subscription plan."""
        return self.assistant_manager.get_assistant_for_user({'subscription_plan': subscription_plan})