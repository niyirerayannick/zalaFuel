from django.apps import AppConfig


class ReportsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "transport.reports"
    label = "atms_reports"
    verbose_name = "ZALA Terminal Reports"
