from django.apps import AppConfig


class FuelConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "transport.fuel"
    label = "atms_fuel"
    verbose_name = "ZALA Terminal Fuel"
