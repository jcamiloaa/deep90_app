from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from model_utils import Choices


class SubscriptionPlan(models.TextChoices):
    """Opciones de planes de suscripción."""
    FREE = 'free', _('Gratuito')
    PREMIUM = 'premium', _('Premium')
    PRO = 'pro', _('Profesional')


class WhatsAppUserStatus(models.TextChoices):
    """Estados posibles para un usuario de WhatsApp."""
    NEW = 'new', _('Nuevo')
    REGISTERED = 'registered', _('Registrado')
    SUSPENDED = 'suspended', _('Suspendido')
    BANNED = 'banned', _('Bloqueado')


class ConversationType(models.TextChoices):
    """Tipos de conversación según el asistente asignado."""
    SYSTEM = 'SYSTEM', _('Sistema')
    GENERAL = 'GENERAL', _('General')
    PREDICTIONS = 'PREDICTIONS', _('Predicciones')
    LIVE_ODDS = 'LIVE_ODDS', _('Cuotas en vivo')
    BETTING = 'BETTING', _('Apuestas')


class WhatsAppUser(models.Model):
    """Modelo para los usuarios de WhatsApp, independiente de User."""
    phone_number = models.CharField(_("Número de teléfono"), max_length=20, primary_key=True)
    profile_name = models.CharField(_("Nombre de perfil"), max_length=255, null=True, blank=True)
    full_name = models.CharField(_("Nombre completo"), max_length=255, null=True, blank=True)
    email = models.EmailField(_("Correo electrónico"), null=True, blank=True)
    birth_date = models.DateField(_("Fecha de nacimiento"), null=True, blank=True)
    country = models.CharField(_("País"), max_length=100, null=True, blank=True)
    city = models.CharField(_("Ciudad"), max_length=100, null=True, blank=True)
    is_blacklisted = models.BooleanField(_("En lista negra"), default=False)
    status = models.CharField(
        _("Estado"),
        max_length=20,
        choices=WhatsAppUserStatus.choices,
        default=WhatsAppUserStatus.NEW
    )
    subscription_plan = models.CharField(
        _("Plan de suscripción"),
        max_length=20,
        choices=SubscriptionPlan.choices,
        default=SubscriptionPlan.FREE
    )
    subscription_expiry = models.DateTimeField(_("Expiración de suscripción"), null=True, blank=True)
    created_at = models.DateTimeField(_("Fecha de creación"), default=timezone.now)
    updated_at = models.DateTimeField(_("Fecha de actualización"), auto_now=True)
    last_activity = models.DateTimeField(_("Última actividad"), default=timezone.now)

    class Meta:
        verbose_name = _("Usuario de WhatsApp")
        verbose_name_plural = _("Usuarios de WhatsApp")
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['subscription_plan']),
            models.Index(fields=['is_blacklisted']),
        ]

    def __str__(self):
        return f"{self.profile_name or self.full_name or self.phone_number}"

    def is_subscription_active(self):
        """
        Verificar si la suscripción está activa.
        
        Returns:
            True si la suscripción es gratuita o si está en periodo activo.
        """
        if self.subscription_plan == SubscriptionPlan.FREE:
            return True
        
        if self.subscription_expiry and self.subscription_expiry > timezone.now():
            return True
        
        return False

    def update_last_activity(self):
        """Actualiza la marca de tiempo de la última actividad."""
        self.last_activity = timezone.now()
        self.save(update_fields=['last_activity'])


class Conversation(models.Model):
    """Modelo para gestionar conversaciones con el asistente."""
    user = models.ForeignKey(
        WhatsAppUser,
        on_delete=models.CASCADE,
        related_name="conversations",
        verbose_name=_("Usuario")
    )
    thread_id = models.CharField(_("ID del hilo"), max_length=100)
    is_active = models.BooleanField(_("Activo"), default=True)
    preserve_context = models.BooleanField(_("Preservar contexto"), default=False, help_text=_("Si es True, el contexto de la conversación se preservará para usuarios premium"))
    conversation_type = models.CharField(
        _("Tipo de conversación"), 
        max_length=20, 
        choices=ConversationType.choices,
        default=ConversationType.GENERAL
    )
    fixture_id = models.CharField(_("ID del partido"), max_length=100, null=True, blank=True, 
                                help_text=_("ID del partido al que se refiere la conversación, si aplica"))
    created_at = models.DateTimeField(_("Fecha de creación"), default=timezone.now)
    updated_at = models.DateTimeField(_("Fecha de actualización"), auto_now=True)
    last_message_at = models.DateTimeField(_("Último mensaje"), auto_now_add=True)

    class Meta:
        verbose_name = _("Conversación")
        verbose_name_plural = _("Conversaciones")
        indexes = [
            models.Index(fields=['thread_id']),
            models.Index(fields=['is_active']),
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['preserve_context']),
            models.Index(fields=['conversation_type']),
        ]

    def __str__(self):
        return f"Conversación {self.id} - {self.user} - {self.conversation_type}"

    def update_last_message_time(self):
        """Actualiza la marca de tiempo del último mensaje."""
        self.last_message_at = timezone.now()
        self.save(update_fields=['last_message_at'])
        
    @property
    def formatted_id(self):
        """
        Devuelve un ID formateado con el thread_id y el tipo de conversación.
        """
        if self.conversation_type == ConversationType.SYSTEM:
            return f"system_conversation_{self.id}"
        else:
            return f"{self.thread_id}_{self.conversation_type}"


class Message(models.Model):
    """Modelo para almacenar mensajes dentro de una conversación."""
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name=_("Conversación")
    )
    message_id = models.CharField(_("ID del mensaje"), max_length=100, null=True, blank=True)
    is_from_user = models.BooleanField(_("Es del usuario"), default=True)
    content = models.TextField(_("Contenido"))
    message_type = models.CharField(_("Tipo de mensaje"), max_length=20, default="text")
    created_at = models.DateTimeField(_("Fecha de creación"), default=timezone.now)
    
    # Nuevos campos para almacenar el JSON completo
    request_json = models.JSONField(_("JSON de solicitud"), null=True, blank=True, 
                                    help_text=_("JSON completo recibido del webhook o enviado a la API"))
    response_json = models.JSONField(_("JSON de respuesta"), null=True, blank=True, 
                                     help_text=_("JSON completo de respuesta de la API o enviado al cliente"))
    
    class Meta:
        verbose_name = _("Mensaje")
        verbose_name_plural = _("Mensajes")
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation']),
            models.Index(fields=['is_from_user']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        direction = "Usuario → Asistente" if self.is_from_user else "Asistente → Usuario"
        return f"{direction}: {self.content[:30]}..."


class UserInput(models.Model):
    """Modelo para registrar inputs del usuario desde formularios de WhatsApp."""
    user = models.ForeignKey(
        WhatsAppUser,
        on_delete=models.CASCADE,
        related_name="inputs",
        verbose_name=_("Usuario")
    )
    flow_id = models.CharField(_("ID del flujo"), max_length=100)
    flow_token = models.CharField(_("Token del flujo"), max_length=255)
    screen_id = models.CharField(_("ID de pantalla"), max_length=100)
    data = models.JSONField(_("Datos del formulario"))
    created_at = models.DateTimeField(_("Fecha de creación"), default=timezone.now)

    class Meta:
        verbose_name = _("Input de usuario")
        verbose_name_plural = _("Inputs de usuario")
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['flow_id']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Input de {self.user} - {self.flow_id}"


class UserPreference(models.Model):
    """Modelo para almacenar preferencias del usuario."""
    user = models.OneToOneField(
        WhatsAppUser,
        on_delete=models.CASCADE,
        related_name="preferences",
        verbose_name=_("Usuario")
    )
    favorite_teams = models.JSONField(_("Equipos favoritos"), default=list, blank=True)
    favorite_leagues = models.JSONField(_("Ligas favoritas"), default=list, blank=True)
    notification_preferences = models.JSONField(_("Preferencias de notificación"), default=dict, blank=True)
    language = models.CharField(_("Idioma"), max_length=10, default="es")
    updated_at = models.DateTimeField(_("Última actualización"), auto_now=True)

    class Meta:
        verbose_name = _("Preferencia de usuario")
        verbose_name_plural = _("Preferencias de usuarios")

    def __str__(self):
        return f"Preferencias de {self.user}"
