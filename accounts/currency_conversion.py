from decimal import Decimal, ROUND_HALF_UP

from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.db import transaction

from .currency import convert_currency


MONEY_FIELD_REGISTRY = {
    "accounts.SystemSettings": ("petrol_unit_price", "diesel_unit_price"),
    "inventory.InventoryRecord": ("unit_cost",),
    "finance.CustomerAccount": ("credit_limit", "balance"),
    "finance.Invoice": ("amount",),
    "finance.Payment": ("amount",),
    "revenue.RevenueEntry": ("amount",),
    "suppliers.FuelPurchaseOrder": ("unit_cost",),
    "suppliers.DeliveryReceipt": ("unit_cost",),
    "sales.ShiftSession": (
        "opening_cash",
        "closing_cash",
        "total_sales",
        "expected_cash",
        "closing_card_total",
        "closing_mobile_total",
        "closing_credit_total",
        "variance_amount",
    ),
    "sales.FuelSale": ("unit_price", "total_amount"),
    "sales.Customer": ("credit_limit", "current_balance"),
    "sales.CreditTransaction": ("amount", "amount_paid"),
    "sales.CreditPayment": ("amount",),
    "sales.OMCSalesEntry": ("unit_price", "total_amount"),
    "atms_orders.Order": ("quoted_price", "profit_estimate"),
    "atms_trips.Trip": (
        "rental_fee",
        "fuel_cost",
        "other_expenses",
        "revenue",
        "total_cost",
        "profit",
        "cost_per_km",
        "revenue_per_km",
    ),
    "atms_finance.Payment": ("amount", "amount_paid"),
    "atms_finance.Expense": ("amount", "fuel_unit_price"),
    "atms_finance.Revenue": ("amount",),
    "atms_finance.DriverAllowance": ("amount",),
    "atms_finance.DriverFee": ("amount",),
    "atms_fuel.FuelRequest": ("amount",),
    "atms_maintenance.MaintenanceRecord": ("cost",),
}


def _quantizer_for_field(field):
    return Decimal("1") if field.decimal_places == 0 else Decimal(10) ** -field.decimal_places


def _converted_value(value, from_currency, to_currency, field):
    if value is None:
        return None
    converted = convert_currency(value, from_currency, to_currency)
    return converted.quantize(_quantizer_for_field(field), rounding=ROUND_HALF_UP)


def convert_system_money_values(from_currency, to_currency, *, exclude_settings_pk=None):
    """
    Convert persisted monetary values when the system currency changes.

    The app stores monetary amounts in the selected system currency. This
    conversion keeps existing rows economically equivalent after Settings is
    changed, e.g. 200 USD becomes the matching RWF amount.
    """
    from_currency = (from_currency or "").upper()
    to_currency = (to_currency or "").upper()
    if not from_currency or not to_currency or from_currency == to_currency:
        return {"converted_rows": 0, "converted_fields": 0}

    converted_rows = 0
    converted_fields = 0

    with transaction.atomic():
        for model_label, field_names in MONEY_FIELD_REGISTRY.items():
            try:
                model = apps.get_model(model_label)
            except (LookupError, ValueError):
                continue

            fields = []
            for field_name in field_names:
                try:
                    fields.append(model._meta.get_field(field_name))
                except FieldDoesNotExist:
                    continue
            if not fields:
                continue

            queryset = model.objects.all()
            if model_label == "accounts.SystemSettings" and exclude_settings_pk is not None:
                queryset = queryset.exclude(pk=exclude_settings_pk)

            for obj in queryset.iterator():
                updates = {}
                for field in fields:
                    old_value = getattr(obj, field.name)
                    if old_value is None:
                        continue
                    new_value = _converted_value(old_value, from_currency, to_currency, field)
                    if new_value != old_value:
                        updates[field.name] = new_value
                        converted_fields += 1
                if updates:
                    model.objects.filter(pk=obj.pk).update(**updates)
                    converted_rows += 1

    return {"converted_rows": converted_rows, "converted_fields": converted_fields}
