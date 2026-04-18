import logging
from email.utils import formataddr
from urllib.parse import urlparse

import dj_database_url
from decouple import Csv, config
from django.core.exceptions import ImproperlyConfigured
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

from .base import *  # noqa: F403,F401

_logger = logging.getLogger("nopra_fuel.settings")


def _env_bool(value, default=False):
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "t", "yes", "y", "on", "debug", "dev"}:
        return True
    if normalized in {"0", "false", "f", "no", "n", "off", "release", "prod", "production"}:
        return False
    return default


DEBUG = _env_bool(config("DEBUG", default=False), default=False)

SECRET_KEY = config("SECRET_KEY", default="").strip()
if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY must be set in production.")
if len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5 or SECRET_KEY.startswith("django-insecure-"):
    raise ImproperlyConfigured("SECRET_KEY is too weak for production. Use a long random value.")

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="", cast=Csv())  # noqa: F405
public_base_url = config("ATMS_PUBLIC_BASE_URL", default="").strip()
if public_base_url:
    parsed_public_url = urlparse(public_base_url)
    if parsed_public_url.hostname and parsed_public_url.hostname not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(parsed_public_url.hostname)
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("Set ALLOWED_HOSTS or ATMS_PUBLIC_BASE_URL in production.")
for host in ("localhost", "127.0.0.1"):
    if host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(host)

CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default=public_base_url or "https://localhost",
    cast=Csv(),
)  # noqa: F405

DATABASE_URL = config("DATABASE_URL", default="sqlite:///app/db.sqlite3")
db_ssl_required = config("DATABASE_SSL_REQUIRE", default=False, cast=bool)
DATABASES = {
    "default": dj_database_url.parse(DATABASE_URL, conn_max_age=600, ssl_require=db_ssl_required)
}  # noqa: F405

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=True, cast=bool)
CSRF_COOKIE_SECURE = config("CSRF_COOKIE_SECURE", default=True, cast=bool)
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=31536000, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True, cast=bool)
SECURE_HSTS_PRELOAD = config("SECURE_HSTS_PRELOAD", default=True, cast=bool)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = (
    "'self'",
    "'unsafe-inline'",
    "https://cdn.jsdelivr.net",
    "https://cdn.tailwindcss.com",
)
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "https://fonts.googleapis.com")
CSP_FONT_SRC = ("'self'", "https://fonts.gstatic.com", "data:")
CSP_IMG_SRC = (
    "'self'",
    "data:",
    "blob:",
    "https://res.cloudinary.com",
    "https:",
)
CSP_CONNECT_SRC = ("'self'", "wss:", "https:")
CSP_FRAME_ANCESTORS = ("'none'",)

if USE_CLOUDINARY:  # noqa: F405
    STORAGES["default"] = {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    }
    DEFAULT_FILE_STORAGE = "cloudinary_storage.storage.MediaCloudinaryStorage"

sentry_dsn = config("SENTRY_DSN", default="")
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=[DjangoIntegration()],
        traces_sample_rate=config("SENTRY_TRACES_SAMPLE_RATE", default=0.1, cast=float),
        send_default_pii=config("SENTRY_SEND_PII", default=False, cast=bool),
    )

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s"
        },
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(name)s %(module)s %(process)d %(thread)d %(message)s"
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        }
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "celery": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "channels": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_USE_SSL = config("EMAIL_USE_SSL", default=False, cast=bool)
EMAIL_TIMEOUT = config("EMAIL_TIMEOUT", default=30, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")

email_backend_override = config("EMAIL_BACKEND", default="").strip()
if email_backend_override:
    EMAIL_BACKEND = email_backend_override
else:
    EMAIL_BACKEND = (
        "django.core.mail.backends.smtp.EmailBackend"
        if (EMAIL_HOST_USER and EMAIL_HOST_PASSWORD)
        else "django.core.mail.backends.console.EmailBackend"
    )

EMAIL_FROM_NAME = config("EMAIL_FROM_NAME", default=f"{BRAND_NAME} Notifications")
EMAIL_FROM_ADDRESS = config(
    "DEFAULT_FROM_EMAIL",
    default=EMAIL_HOST_USER or "no-reply@zalaeco.local",
)
DEFAULT_FROM_EMAIL = formataddr((EMAIL_FROM_NAME, EMAIL_FROM_ADDRESS))

if EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
    _logger.warning(
        "Production email is using console backend. "
        "Set EMAIL_HOST_USER and EMAIL_HOST_PASSWORD in Coolify to enable real SMTP."
    )
