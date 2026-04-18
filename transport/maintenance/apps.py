from django.apps import AppConfig


class MaintenanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "transport.maintenance"
    label = "atms_maintenance"
    verbose_name = "ZALA/ECO ENERGY Maintenance"
