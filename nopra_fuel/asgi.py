import os

from django.core.asgi import get_asgi_application

# Default to development settings locally; production can override DJANGO_SETTINGS_MODULE
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nopra_fuel.settings.development")

application = get_asgi_application()
