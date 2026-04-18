from decimal import Decimal, ROUND_HALF_UP

from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.db import transaction

from .currency import convert_currency


MONEY_FIELD_REGISTRY = {
    "accounts.SystemSettings": ("petrol_unit_price", "diesel_unit_price"),
    "finance.CustomerAccount": ("credit_limit", "balance"),
    "finance.Invoice": ("amount",),
    "finance.Payment": ("amount",),
    "sales.ShiftSession": ("opening_cash", "closing_cash", "total_sales"),
    "sales.FuelSale": ("unit_price", "total_amount"),
    "sales.Customer": ("credit_limit", "current_balance"),
    "sales.CreditTransaction": ("amount",),
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
                update_fields = []
                for field in fields:
                    old_value = getattr(obj, field.name)
                    if old_value is None:
                        continue
                    new_value = _converted_value(old_value, from_currency, to_currency, field)
                    if new_value != old_value:
                        setattr(obj, field.name, new_value)
                        update_fields.append(field.name)
                        converted_fields += 1
                if update_fields:
                    obj.save(update_fields=update_fields)
                    converted_rows += 1

    return {"converted_rows": converted_rows, "converted_fields": converted_fields}
