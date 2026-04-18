from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "transport.orders"
    label = "atms_orders"
    verbose_name = "Orders"
