from django.apps import AppConfig


class RoutesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "transport.routes"
    label = "atms_routes"
    verbose_name = "ZALA/ECO ENERGY Routes"
