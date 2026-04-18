from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "transport.core"
    label = "atms_core"
    verbose_name = "ZALA/ECO ENERGY Core"
