"""
Real-time currency conversion utility.

Uses the free ExchangeRate-API (https://open.er-api.com) — no API key required.
Rates are cached in the database for 1 hour to avoid hitting rate limits.
"""
import json
import logging
from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.utils import timezone

logger = logging.getLogger(__name__)

# Free public API — no key needed, 1500 requests/month
EXCHANGE_RATE_API_URL = "https://open.er-api.com/v6/latest/{base}"

# Fallback rates (approximate) in case the API is unreachable
FALLBACK_RATES = {
    "USD": {
        "RWF": Decimal("1459.00"),
        "EUR": Decimal("0.92"),
        "GBP": Decimal("0.79"),
        "KES": Decimal("129.00"),
        "UGX": Decimal("3750.00"),
        "TZS": Decimal("2650.00"),
        "SLE": Decimal("23.01"),
        "USD": Decimal("1.00"),
    },
    "RWF": {
        "USD": Decimal("0.00069"),
        "EUR": Decimal("0.000667"),
        "GBP": Decimal("0.000573"),
        "KES": Decimal("0.0935"),
        "UGX": Decimal("2.717"),
        "TZS": Decimal("1.920"),
        "SLE": Decimal("0.01577"),
        "RWF": Decimal("1.00"),
    },
    "SLE": {
        "USD": Decimal("0.04346"),
        "EUR": Decimal("0.03998"),
        "GBP": Decimal("0.03433"),
        "RWF": Decimal("63.41"),
        "KES": Decimal("5.61"),
        "UGX": Decimal("162.97"),
        "TZS": Decimal("115.17"),
        "SLE": Decimal("1.00"),
    },
}

# Currency display symbols
CURRENCY_SYMBOLS = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "RWF": "FRw",
    "KES": "KSh",
    "UGX": "USh",
    "TZS": "TSh",
    "SLE": "Le",
}

# How many decimal places per currency
CURRENCY_DECIMALS = {
    "USD": 2,
    "EUR": 2,
    "GBP": 2,
    "RWF": 0,  # no decimals for Rwandan Franc
    "KES": 2,
    "UGX": 0,
    "TZS": 0,
    "SLE": 2,
}

CACHE_DURATION = timedelta(hours=1)


def _fallback_rates_for(base_currency: str) -> dict:
    direct_rates = dict(FALLBACK_RATES.get(base_currency, {}))
    usd_rates = FALLBACK_RATES["USD"]

    if base_currency == "USD":
        return {k: float(v) for k, v in usd_rates.items()}

    usd_to_base = usd_rates.get(base_currency)
    if usd_to_base:
        for target_currency, usd_to_target in usd_rates.items():
            if target_currency not in direct_rates:
                direct_rates[target_currency] = usd_to_target / usd_to_base
        direct_rates[base_currency] = Decimal("1.00")

    if direct_rates:
        return {k: float(v) for k, v in direct_rates.items()}

    return {k: float(v) for k, v in usd_rates.items()}


def _fetch_rates_from_api(base_currency: str) -> dict | None:
    """Fetch exchange rates from the free public API."""
    import urllib.request
    import urllib.error

    url = EXCHANGE_RATE_API_URL.format(base=base_currency)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ZALA-ECO/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
            if data.get("result") == "success":
                return data.get("rates", {})
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
        logger.warning("Currency API fetch failed for %s: %s", base_currency, exc)
    return None


def _get_cached_rates(base_currency: str) -> dict | None:
    """Return cached rates if still fresh, else None."""
    from .models import SystemSettings

    settings = SystemSettings.get_settings()
    if settings is None:
        return None

    cache_key = f"exchange_rates_{base_currency}"
    cached = getattr(settings, "_rate_cache", {})

    # We store cached rates in a simple JSON text field on the model
    try:
        cache_data = json.loads(settings.exchange_rate_cache or "{}")
    except (json.JSONDecodeError, TypeError):
        cache_data = {}

    entry = cache_data.get(cache_key)
    if entry:
        fetched_at = timezone.datetime.fromisoformat(entry["fetched_at"])
        if timezone.is_naive(fetched_at):
            fetched_at = timezone.make_aware(fetched_at)
        if timezone.now() - fetched_at < CACHE_DURATION:
            return entry["rates"]
    return None


def _save_cached_rates(base_currency: str, rates: dict):
    """Persist rates to the SystemSettings cache field."""
    from .models import SystemSettings

    settings = SystemSettings.get_settings()
    if settings is None:
        return

    try:
        cache_data = json.loads(settings.exchange_rate_cache or "{}")
    except (json.JSONDecodeError, TypeError):
        cache_data = {}

    cache_key = f"exchange_rates_{base_currency}"
    cache_data[cache_key] = {
        "rates": rates,
        "fetched_at": timezone.now().isoformat(),
    }

    SystemSettings.objects.filter(pk=settings.pk).update(
        exchange_rate_cache=json.dumps(cache_data)
    )


def get_exchange_rates(base_currency: str = "USD") -> dict:
    """
    Get exchange rates for the given base currency.
    Returns a dict like {"RWF": 1380.0, "EUR": 0.92, ...}
    Uses cache, then API, then fallback.
    """
    base_currency = base_currency.upper()

    # 1. Try cache
    cached = _get_cached_rates(base_currency)
    if cached:
        return cached

    # 2. Try live API
    rates = _fetch_rates_from_api(base_currency)
    if rates:
        _save_cached_rates(base_currency, rates)
        return rates

    # 3. Fallback
    return _fallback_rates_for(base_currency)


def convert_currency(
    amount,
    from_currency: str = "USD",
    to_currency: str = "RWF",
) -> Decimal:
    """Convert an amount between two currencies."""
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()
    try:
        normalized_amount = Decimal(str(amount or 0))
    except (InvalidOperation, TypeError, ValueError):
        normalized_amount = Decimal("0")

    if from_currency == to_currency:
        return normalized_amount

    rates = get_exchange_rates(from_currency)
    rate = rates.get(to_currency)

    if rate is None:
        # Try reverse
        reverse_rates = get_exchange_rates(to_currency)
        reverse_rate = reverse_rates.get(from_currency)
        if reverse_rate and float(reverse_rate) != 0:
            rate = 1.0 / float(reverse_rate)
        else:
            logger.error("No rate found for %s → %s", from_currency, to_currency)
            return normalized_amount

    result = normalized_amount * Decimal(str(rate))
    decimals = CURRENCY_DECIMALS.get(to_currency, 2)
    quant = Decimal("1") if decimals == 0 else Decimal(10) ** -decimals
    return result.quantize(quant, rounding=ROUND_HALF_UP)


def format_currency(amount, currency_code: str = "USD") -> str:
    """Format a currency amount with symbol and correct decimal places."""
    currency_code = currency_code.upper()
    symbol = CURRENCY_SYMBOLS.get(currency_code, currency_code)
    decimals = CURRENCY_DECIMALS.get(currency_code, 2)

    try:
        value = Decimal(str(amount))
    except Exception:
        value = Decimal("0")

    quant = Decimal("1") if decimals == 0 else Decimal(10) ** -decimals
    value = value.quantize(quant, rounding=ROUND_HALF_UP)

    # Format with thousand separators
    if decimals == 0:
        formatted = f"{int(value):,}"
    else:
        formatted = f"{value:,.{decimals}f}"

    return f"{symbol} {formatted}"
