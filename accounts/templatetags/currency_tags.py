"""
Template tags for currency formatting and conversion.

All monetary amounts in the database are stored in the active system currency.
When the system currency changes, the settings save workflow converts existing
money values once. Template filters therefore format system-currency values by
default and only convert when an explicit target currency is provided.
"""
from decimal import Decimal

from django import template
from django.conf import settings as django_settings

from accounts.currency import CURRENCY_SYMBOLS, convert_currency, format_currency

register = template.Library()


def _get_system_currency():
    """Get the configured system currency code."""
    from accounts.models import SystemSettings

    try:
        system_settings = SystemSettings.get_settings()
        if system_settings:
            return system_settings.currency or getattr(django_settings, "DEFAULT_CURRENCY", "USD")
    except Exception:
        pass
    return getattr(django_settings, "DEFAULT_CURRENCY", "USD")


@register.filter(name="currency")
def currency_filter(amount, target_currency=None):
    """
    Format a system-currency amount.

    If target_currency is provided, convert from the current system currency to
    that target before formatting.
    """
    if amount is None:
        amount = 0

    system_currency = _get_system_currency()
    display_currency = target_currency.upper() if target_currency else system_currency
    if display_currency != system_currency:
        amount = convert_currency(amount, system_currency, display_currency)

    return format_currency(amount, display_currency)


@register.filter(name="format_only")
def format_only_filter(amount, currency_code=None):
    """
    Format an amount with the currency symbol but do not convert it.
    Use this when the amount is already in the target currency.
    """
    if amount is None:
        amount = 0

    code = currency_code.upper() if currency_code else _get_system_currency()
    return format_currency(amount, code)


@register.filter(name="currency_raw")
def currency_raw_filter(amount, target_currency=None):
    """
    Return a raw Decimal amount.

    If target_currency is provided, convert from the current system currency to
    that target first. Useful for JS or template-side calculations.
    """
    if amount is None:
        amount = 0

    system_currency = _get_system_currency()
    display_currency = target_currency.upper() if target_currency else system_currency
    if display_currency != system_currency:
        return convert_currency(amount, system_currency, display_currency)

    return Decimal(str(amount))


@register.filter(name="convert")
def convert_filter(amount, to_currency):
    """Explicitly convert amount from system currency to to_currency and format it."""
    if amount is None:
        amount = 0

    to_currency = (to_currency or _get_system_currency()).upper()
    converted = convert_currency(amount, _get_system_currency(), to_currency)
    return format_currency(converted, to_currency)


@register.filter(name="convert_raw")
def convert_raw_filter(amount, to_currency):
    """Convert amount from system currency to to_currency and return a raw Decimal."""
    if amount is None:
        amount = 0

    to_currency = (to_currency or _get_system_currency()).upper()
    return convert_currency(amount, _get_system_currency(), to_currency)


@register.simple_tag(name="currency_sym")
def currency_sym_tag():
    """Return just the system currency symbol."""
    code = _get_system_currency()
    return CURRENCY_SYMBOLS.get(code, code)
