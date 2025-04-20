from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import WhatsAppUser, Conversation, Message, UserInput


@receiver(post_save, sender=Message)
def update_conversation_last_message_time(sender, instance, **kwargs):
    """Actualiza la marca de tiempo del último mensaje en la conversación."""
    conversation = instance.conversation
    conversation.last_message_at = instance.created_at
    conversation.save(update_fields=['last_message_at'])


@receiver(post_save, sender=Message)
def update_user_last_activity(sender, instance, **kwargs):
    """Actualiza la marca de tiempo de la última actividad del usuario cuando envía un mensaje."""
    if instance.is_from_user:
        user = instance.conversation.user
        user.last_activity = instance.created_at
        user.save(update_fields=['last_activity'])


@receiver(post_save, sender=UserInput)
def process_user_input_data(sender, instance, created, **kwargs):
    """Procesa los datos de entrada del usuario cuando se recibe un formulario completado."""
    if created and instance.flow_id == 'registration':
        # Procesar datos del formulario de registro
        user = instance.user
        data = instance.data
        
        if 'name' in data and data['name']:
            user.full_name = data['name']
        
        if 'email' in data and data['email']:
            user.email = data['email']
        
        if 'birth_date' in data and data['birth_date']:
            try:
                user.birth_date = timezone.datetime.strptime(
                    data['birth_date'], '%Y-%m-%d'
                ).date()
            except (ValueError, TypeError):
                pass
        
        if 'country' in data and data['country']:
            user.country = data['country']
        
        if 'city' in data and data['city']:
            user.city = data['city']
        
        # Actualizar estado del usuario a registrado si tenemos la información básica
        if user.full_name and user.email:
            user.status = 'registered'
        
        user.save()