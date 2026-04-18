from django.apps import AppConfig


class TripsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "transport.trips"
    label = "atms_trips"
    verbose_name = "ZALA Terminal Trips"

    def ready(self):
        from . import signals  # noqa: F401
