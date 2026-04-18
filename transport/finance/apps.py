from django.apps import AppConfig


class FinanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "transport.finance"
    label = "atms_finance"
    verbose_name = "ZALA Terminal Finance"

    def ready(self):
        import transport.finance.signals  # noqa: F401
