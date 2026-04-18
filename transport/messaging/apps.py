from django.apps import AppConfig


class MessagingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "transport.messaging"
    label = "atms_messaging"
    verbose_name = "ZALA Terminal Messaging"

    def ready(self):
        from . import signals  # noqa: F401
