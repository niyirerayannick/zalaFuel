from django.conf import settings as django_settings

from .models import SystemSettings
from .currency import CURRENCY_SYMBOLS
# Transport analytics removed in fuel edition; provide a safe stub
def user_notification_payload(_user):
    return {
        "notifications": [],
        "notification_count": 0,
        "support_chat_unread_count": 0,
    }


def system_settings(request):
    """Make system settings available to all templates"""
    try:
        settings = SystemSettings.get_settings()
    except Exception:
        settings = None
    
    brand_name = getattr(
        django_settings,
        "BRAND_NAME",
        "ZALA/ECO ENERGY",
    )
    
    # Define the color mapping
    color_map = {
        'blue': {
            'primary': 'blue',
            'bg': 'bg-blue-600',
            'bg_hover': 'hover:bg-blue-700',
            'bg_light': 'bg-blue-50',
            'text': 'text-blue-700',
            'ring': 'ring-blue-500',
            'border': 'border-blue-600',
        },
        'green': {
            'primary': 'green',
            'bg': 'bg-green-600',
            'bg_hover': 'hover:bg-green-700',
            'bg_light': 'bg-green-50',
            'text': 'text-green-700',
            'ring': 'ring-green-500',
            'border': 'border-green-600',
        },
        'purple': {
            'primary': 'purple',
            'bg': 'bg-purple-600',
            'bg_hover': 'hover:bg-purple-700',
            'bg_light': 'bg-purple-50',
            'text': 'text-purple-700',
            'ring': 'ring-purple-500',
            'border': 'border-purple-600',
        },
        'red': {
            'primary': 'red',
            'bg': 'bg-red-600',
            'bg_hover': 'hover:bg-red-700',
            'bg_light': 'bg-red-50',
            'text': 'text-red-700',
            'ring': 'ring-red-500',
            'border': 'border-red-600',
        },
        'orange': {
            'primary': 'orange',
            'bg': 'bg-orange-600',
            'bg_hover': 'hover:bg-orange-700',
            'bg_light': 'bg-orange-50',
            'text': 'text-orange-700',
            'ring': 'ring-orange-500',
            'border': 'border-orange-600',
        },
    }
    
    theme_color = 'blue'  # default
    currency_code = getattr(django_settings, "DEFAULT_CURRENCY", "USD")
    currency_symbol = CURRENCY_SYMBOLS.get(currency_code, currency_code)
    
    if settings:
        theme_color = settings.primary_color or 'blue'
        currency_code = settings.currency or currency_code
        currency_symbol = settings.currency_symbol or CURRENCY_SYMBOLS.get(currency_code, currency_code)

    notification_payload = {
        "notifications": [],
        "notification_count": 0,
        "support_chat_unread_count": 0,
    }
    if getattr(request, "user", None) and request.user.is_authenticated:
        try:
            notification_payload = user_notification_payload(request.user)
        except Exception:
            notification_payload = {
                "notifications": [],
                "notification_count": 0,
                "support_chat_unread_count": 0,
            }
    
    return {
        'system_settings': settings,
        'theme': color_map.get(theme_color, color_map['blue']),
        'currency_symbol': currency_symbol,
        'currency_code': currency_code,
        'brand_name': brand_name,
        **notification_payload,
    }
