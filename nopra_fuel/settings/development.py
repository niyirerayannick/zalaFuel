from .base import *  # noqa: F403,F401
import os
from email.utils import formataddr
from decouple import config

DEBUG = True

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Email configuration: default to console backend for development.
# To enable real SMTP, set EMAIL_HOST_USER and EMAIL_HOST_PASSWORD in .env.
EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")

if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_FROM_NAME = config("EMAIL_FROM_NAME", default="ZALA/ECO ENERGY Notifications")
    EMAIL_FROM_ADDRESS = config("DEFAULT_FROM_EMAIL", default=EMAIL_HOST_USER)
    DEFAULT_FROM_EMAIL = formataddr((EMAIL_FROM_NAME, EMAIL_FROM_ADDRESS))
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

INTERNAL_IPS = ["127.0.0.1"]

# Allow ngrok tunnel for Twilio webhook development
ALLOWED_HOSTS = ["*"]
CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1:8080",
    "http://localhost:8080",
    "https://poor-arlette-unnettled.ngrok-free.dev",
]

# Twilio status callback via ngrok
TWILIO_STATUS_CALLBACK_URL = "https://poor-arlette-unnettled.ngrok-free.dev/api/whatsapp/status/"

# Use Local Memory Cache for development to avoid Redis dependency
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
    }
}

# Use In-Memory Channel Layer for development
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}
