from django.apps import AppConfig


class CustomersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "transport.customers"
    label = "atms_customers"
    verbose_name = "ZALA Terminal Customers"
