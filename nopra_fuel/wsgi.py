import os

from django.core.wsgi import get_wsgi_application

# Default to development settings locally; production can override DJANGO_SETTINGS_MODULE
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nopra_fuel.settings.development")

application = get_wsgi_application()
