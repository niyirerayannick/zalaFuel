from django.apps import AppConfig


class DriversConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "transport.drivers"
    label = "atms_drivers"
    verbose_name = "ZALA/ECO ENERGY Drivers"
