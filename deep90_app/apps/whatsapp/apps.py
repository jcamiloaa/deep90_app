from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class WhatsAppConfig(AppConfig):
    name = "deep90_app.apps.whatsapp"
    verbose_name = _("WhatsApp")

    def ready(self):
        try:
            import deep90_app.apps.whatsapp.signals  # noqa F401
        except ImportError:
            pass
