from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "transport.analytics"
    label = "atms_analytics"
    verbose_name = "ZALA Terminal Analytics"
