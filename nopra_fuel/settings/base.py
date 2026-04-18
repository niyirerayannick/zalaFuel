from pathlib import Path
from email.utils import formataddr
from urllib.parse import urlparse

import dj_database_url
from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

BRAND_NAME = "ZALA Terminal"


def _env_bool(name, default=False):
    value = config(name, default=str(default))
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "t", "yes", "y", "on", "debug", "dev"}:
        return True
    if normalized in {"0", "false", "f", "no", "n", "off", "release", "prod", "production"}:
        return False
    return default


SECRET_KEY = config("SECRET_KEY", default="django-insecure-change-this-in-production")
DEBUG = _env_bool("DEBUG", default=False)

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="127.0.0.1,localhost", cast=Csv())
CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="http://127.0.0.1:8000,http://localhost:8000",
    cast=Csv(),
)
ATMS_PUBLIC_BASE_URL = config("ATMS_PUBLIC_BASE_URL", default="http://127.0.0.1:8000")
parsed_public_url = urlparse(ATMS_PUBLIC_BASE_URL)
public_hostname = parsed_public_url.hostname
if public_hostname and public_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(public_hostname)

DJANGO_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
]

THIRD_PARTY_APPS = [
    "channels",
    "tailwind",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "storages",
    "cloudinary",
    "cloudinary_storage",
    "csp",
]

LOCAL_APPS = [
    "theme",
    "accounts",
    "core",
    "dashboard",
    "terminals",
    "products",
    "tanks",
    "receipts",
    "dispatches",
    "omcs",
    "stations",
    "inventory",
    "sales",
    "finance",
    "revenue",
    "analytics",
    "suppliers",
    "reports",
    "notifications",
    "monitoring",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.ActiveStationMiddleware",
    "accounts.middleware.RBACMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "csp.middleware.CSPMiddleware",
]

ROOT_URLCONF = "nopra_fuel.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "accounts.context_processors.system_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "nopra_fuel.wsgi.application"
ASGI_APPLICATION = "nopra_fuel.asgi.application"

DATABASE_URL = config("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
DATABASES = {
    "default": dj_database_url.parse(DATABASE_URL, conn_max_age=600, ssl_require=False)
}

REDIS_URL = config("REDIS_URL", default="").strip()

if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "zalaeco-default-cache",
        }
    }
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = config("TIME_ZONE", default="Africa/Johannesburg")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"

SITE_ID = config("SITE_ID", default=1, cast=int)

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
LOGIN_URL = "/"
LOGIN_REDIRECT_URL = "/"

EMAIL_BACKEND = config(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
EMAIL_FROM_NAME = config("EMAIL_FROM_NAME", default=f"{BRAND_NAME} Notifications")
EMAIL_FROM_ADDRESS = config("DEFAULT_FROM_EMAIL", default="no-reply@zalaeco.local")
DEFAULT_FROM_EMAIL = formataddr((EMAIL_FROM_NAME, EMAIL_FROM_ADDRESS))
DEFAULT_CURRENCY = config("DEFAULT_CURRENCY", default="USD").upper()

TAILWIND_APP_NAME = config("TAILWIND_APP_NAME", default="theme")

USE_CLOUDINARY = config("USE_CLOUDINARY", default=False, cast=bool)
CLOUDINARY_URL = config("CLOUDINARY_URL", default="")
CLOUDINARY_STORAGE = {
    "CLOUD_NAME": config("CLOUDINARY_CLOUD_NAME", default=""),
    "API_KEY": config("CLOUDINARY_API_KEY", default=""),
    "API_SECRET": config("CLOUDINARY_API_SECRET", default=""),
    "SECURE": True,
    "PREFIX": "",
}

if USE_CLOUDINARY:
    STORAGES["default"] = {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    }
    DEFAULT_FILE_STORAGE = "cloudinary_storage.storage.MediaCloudinaryStorage"

CELERY_BROKER_URL = config("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default=REDIS_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# Twilio WhatsApp integration
TWILIO_ACCOUNT_SID = config("TWILIO_ACCOUNT_SID", default="")
TWILIO_AUTH_TOKEN = config("TWILIO_AUTH_TOKEN", default="")
TWILIO_SMS_NUMBER = config("TWILIO_SMS_NUMBER", default="")
TWILIO_MESSAGING_SERVICE_SID = config("TWILIO_MESSAGING_SERVICE_SID", default="")
TWILIO_WHATSAPP_NUMBER = config("TWILIO_WHATSAPP_NUMBER", default="")
TWILIO_STATUS_CALLBACK_URL = config("TWILIO_STATUS_CALLBACK_URL", default="")
MAINTENANCE_SERVICE_TYPES_URL = config("MAINTENANCE_SERVICE_TYPES_URL", default="")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(name)s %(module)s %(process)d %(thread)d %(message)s"
        },
        "simple": {"format": "%(levelname)s %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        }
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "celery": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "channels": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = (
    "'self'",
    "'unsafe-inline'",
    "https://cdn.tailwindcss.com",
    "https://cdn.jsdelivr.net",
)
CSP_STYLE_SRC = (
    "'self'",
    "'unsafe-inline'",
    "https://fonts.googleapis.com",
)
CSP_FONT_SRC = (
    "'self'",
    "https://fonts.gstatic.com",
    "data:",
)
CSP_IMG_SRC = (
    "'self'",
    "data:",
    "blob:",
    "https:",
)
