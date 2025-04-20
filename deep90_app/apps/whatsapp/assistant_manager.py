import logging
import json
from django.conf import settings
from openai import OpenAI

from .sports_service import FootballDataService
from .models import SubscriptionPlan

logger = logging.getLogger(__name__)


class AssistantManager:
    """
    Clase para gestionar la interacción con el asistente OpenAI,
    incluyendo la configuración de funciones personalizadas.
    """
    
    def __init__(self):
        """Inicializar el cliente OpenAI y cargar IDs de asistentes."""
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.assistant_id_free = settings.ASSISTANT_ID_FREE
        self.assistant_id_pay = settings.ASSISTANT_ID_PAY
        self.assistant_id_pro = settings.ASSISTANT_ID_PRO
    
    def get_assistant_for_user(self, user):
        """
        Determina qué asistente usar basado en la suscripción del usuario.
        
        Args:
            user: Objeto WhatsAppUser
            
        Returns:
            ID del asistente apropiado
        """
        if user.subscription_plan == SubscriptionPlan.PRO:
            return self.assistant_id_pro
        elif user.subscription_plan == SubscriptionPlan.PREMIUM:
            return self.assistant_id_pay
        return self.assistant_id_free
    
    def create_thread(self):
        """
        Crea un nuevo hilo de conversación.
        
        Returns:
            ID del hilo creado
        """
        try:
            thread = self.client.beta.threads.create()
            return thread.id
        except Exception as e:
            logger.error(f"Error al crear thread: {e}")
            raise
    
    def add_message_to_thread(self, thread_id, content, user_info=None):
        """
        Añade un mensaje del usuario al hilo.
        
        Args:
            thread_id: ID del hilo
            content: Contenido del mensaje
            user_info: Información del usuario (opcional)
            
        Returns:
            Objeto mensaje creado
        """
        try:
            metadata = {}
            if user_info:
                metadata = {'user_info': json.dumps(user_info)}
                
            message = self.client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=content,
                metadata=metadata
            )
            return message
        except Exception as e:
            logger.error(f"Error al añadir mensaje al thread: {e}")
            raise
    
    def run_assistant(self, thread_id, assistant_id, tools_config=None):
        """
        Ejecuta el asistente en un hilo, opcionalmente con configuración de tools.
        
        Args:
            thread_id: ID del hilo
            assistant_id: ID del asistente
            tools_config: Configuración adicional para las herramientas (opcional)
            
        Returns:
            ID de la ejecución
        """
        try:
            # Prepara las funciones disponibles
            available_tools = self._get_available_tools(tools_config)
            
            # Ejecuta el asistente
            run = self.client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=assistant_id,
                tools=available_tools
            )
            
            return run.id
        except Exception as e:
            logger.error(f"Error al ejecutar asistente: {e}")
            raise
    
    def check_run_status(self, thread_id, run_id):
        """
        Verifica el estado de una ejecución.
        
        Args:
            thread_id: ID del hilo
            run_id: ID de la ejecución
            
        Returns:
            Estado de la ejecución
        """
        try:
            # Intento con tiempo de espera más largo para evitar problemas de timeout
            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run_id
            )
            return run
        except Exception as e:
            logger.error(f"Error al verificar estado de ejecución: {e}")
            # En caso de error al verificar el estado, lo manejamos adecuadamente
            # para que no falle todo el sistema
            from openai.types.beta.threads import Run
            from openai.types.beta.threads.run import RunStatus
            
            # Crear un objeto Run simulado con estado de error para manejar el fallo de manera controlada
            class MockRun:
                def __init__(self):
                    self.status = "failed"
                    self.id = run_id
                    self.thread_id = thread_id
                    self.required_action = None
            
            return MockRun()
    
    def process_tool_calls(self, thread_id, run_id, required_action):
        """
        Procesa las llamadas a tools del asistente.
        
        Args:
            thread_id: ID del hilo
            run_id: ID de la ejecución
            required_action: Acción requerida con las herramientas a llamar
            
        Returns:
            Estado de la ejecución actualizada
        """
        try:
            tool_calls = required_action.submit_tool_outputs.tool_calls
            tool_outputs = []
            
            for tool_call in tool_calls:
                # Procesar cada llamada a herramienta
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                # Ejecutar la función correspondiente
                output = self._execute_tool_function(function_name, function_args)
                
                # Agregar resultado a los outputs
                tool_outputs.append({
                    "tool_call_id": tool_call.id,
                    "output": output
                })
            
            # Enviar los resultados de las herramientas
            run = self.client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread_id,
                run_id=run_id,
                tool_outputs=tool_outputs
            )
            
            return run
        except Exception as e:
            logger.error(f"Error al procesar tool calls: {e}")
            raise
    
    def get_assistant_messages(self, thread_id, after_message_id=None):
        """
        Obtiene los mensajes del asistente después de un ID de mensaje específico.
        
        Args:
            thread_id: ID del hilo
            after_message_id: ID del mensaje después del cual obtener mensajes
            
        Returns:
            Lista de mensajes del asistente
        """
        try:
            # Obtener todos los mensajes del hilo
            response = self.client.beta.threads.messages.list(
                thread_id=thread_id,
                order="desc"  # Más recientes primero
            )
            
            messages = []
            
            # Si se especifica un mensaje_id, recoger mensajes hasta ese ID
            # De lo contrario, recoger todos los mensajes del asistente
            for message in response.data:
                if message.role == "assistant":
                    if after_message_id and message.id == after_message_id:
                        break
                    
                    # Extraer contenido del mensaje
                    content = []
                    for content_part in message.content:
                        if content_part.type == "text":
                            content.append(content_part.text.value)
                    
                    messages.append({
                        "id": message.id,
                        "content": "\n".join(content),
                        "created_at": message.created_at
                    })
            
            return messages
        except Exception as e:
            logger.error(f"Error al obtener mensajes del asistente: {e}")
            raise
    
    def _get_available_tools(self, tools_config=None):
        """
        Devuelve la lista de herramientas disponibles para el asistente.
        """
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_live_match_results",
                    "description": "Always call this function to get the latest live football match results, even if you have already called it before in the same conversation. The data is updated every 15 seconds, so you should use it whenever the user asks about a match or requests updated results.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False,
                        "required": []
                    }
                }
            }
        ]
        return tools
    
    def _execute_tool_function(self, function_name, function_args):
        """
        Ejecuta una función de herramienta específica.
        
        Args:
            function_name: Nombre de la función a ejecutar
            function_args: Argumentos para la función
            
        Returns:
            Resultado de la función como string
        """
        try:
            # Mapear nombres de funciones a funciones reales
            function_map = {
                "get_live_match_results": FootballDataService.get_live_match_results
            }
            
            # Verificar si la función existe
            if function_name not in function_map:
                return f"Error: Función '{function_name}' no implementada."
            
            # Ejecutar la función
            result = function_map[function_name](**function_args)
            return result
        
        except Exception as e:
            logger.error(f"Error al ejecutar función {function_name}: {e}")
            return f"Error al ejecutar {function_name}: {str(e)}"