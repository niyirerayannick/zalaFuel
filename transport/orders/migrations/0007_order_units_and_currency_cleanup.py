from decimal import Decimal
import re

from django.conf import settings
from django.db import migrations, models
from django.utils import timezone
import django.db.models.deletion


UNIT_DEFINITIONS = [
    ("Kilogram", "kg", "weight"),
    ("Piece", "pcs", "count"),
    ("Box", "box", "count"),
    ("Ton", "ton", "weight"),
    ("Liter", "L", "volume"),
    ("Cubic Meter", "m3", "volume"),
]


def _format_quantity(value):
    normalized = Decimal(str(value or 0))
    formatted = format(normalized, "f")
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted or "0"


def _pick_unit_symbol(quantity_text, commodity_type):
    text = (quantity_text or "").lower()
    if any(token in text for token in ["cubic meter", "cubic meters", "m3", "m^3", "m³"]):
        return "m3"
    if any(token in text for token in ["kilogram", "kilograms", "kg"]):
        return "kg"
    if any(token in text for token in ["ton", "tons", "tonne", "tonnes"]):
        return "ton"
    if any(token in text for token in ["box", "boxes"]):
        return "box"
    if any(token in text for token in ["piece", "pieces", "pcs"]):
        return "pcs"
    fuel_types = {"diesel", "petrol", "jet_a1", "bitumen"}
    if commodity_type in fuel_types or any(token in text for token in ["liter", "liters", "litre", "litres", "l "]):
        return "L"
    return "kg"


def seed_units_and_backfill_orders(apps, schema_editor):
    Unit = apps.get_model("atms_orders", "Unit")
    Order = apps.get_model("atms_orders", "Order")
    SystemSettings = apps.get_model("accounts", "SystemSettings")

    units_by_symbol = {}
    for name, symbol, measurement_category in UNIT_DEFINITIONS:
        unit, _created = Unit.objects.get_or_create(
            symbol=symbol,
            defaults={
                "name": name,
                "measurement_category": measurement_category,
                "is_active": True,
            },
        )
        units_by_symbol[symbol] = unit

    for order in Order.objects.all():
        symbol = _pick_unit_symbol(getattr(order, "quantity", ""), getattr(order, "commodity_type", ""))
        unit = units_by_symbol.get(symbol)

        updates = {"unit_id": unit.pk if unit else None}

        estimated_weight = getattr(order, "estimated_weight", None)
        estimated_volume = getattr(order, "estimated_volume", None)
        if estimated_weight:
            updates["measurement_type"] = "weight"
            updates["weight_or_volume"] = float(estimated_weight)
        elif estimated_volume:
            updates["measurement_type"] = "volume"
            updates["weight_or_volume"] = float(estimated_volume)
        else:
            updates["measurement_type"] = None
            updates["weight_or_volume"] = None

        total_quantity = getattr(order, "total_quantity", None)
        if total_quantity in (None, ""):
            quantity_text = getattr(order, "quantity", "") or ""
            match = re.search(r"[-+]?\d*\.?\d+", quantity_text)
            total_quantity = Decimal(match.group()) if match else Decimal("0")
        updates["total_quantity"] = float(total_quantity or 0)

        display_quantity = updates["total_quantity"]
        unit_symbol = getattr(unit, "symbol", "")
        if display_quantity and unit_symbol:
            quantity_text = f"{_format_quantity(display_quantity)} {unit_symbol}"
        elif display_quantity:
            quantity_text = _format_quantity(display_quantity)
        else:
            quantity_text = getattr(order, "quantity", "")
        updates["quantity"] = quantity_text

        Order.objects.filter(pk=order.pk).update(**updates)

    default_currency = getattr(settings, "DEFAULT_CURRENCY", "USD")
    currency_symbol_map = {
        "USD": "$",
        "EUR": "EUR",
        "GBP": "GBP",
        "RWF": "FRw",
        "KES": "KSh",
        "UGX": "USh",
        "TZS": "TSh",
    }
    SystemSettings.objects.filter(currency="").update(currency=default_currency)
    SystemSettings.objects.filter(currency_symbol="").update(
        currency_symbol=currency_symbol_map.get(default_currency, default_currency)
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("accounts", "0011_user_session_invalid_before"),
        ("atms_orders", "0006_order_payment_terms"),
    ]

    operations = [
        migrations.CreateModel(
            name="Unit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True)),
                ("symbol", models.CharField(max_length=20, unique=True)),
                ("measurement_category", models.CharField(choices=[("count", "Count"), ("weight", "Weight"), ("volume", "Volume")], default="count", max_length=20)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(default=timezone.now)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.AddField(
            model_name="order",
            name="measurement_type",
            field=models.CharField(blank=True, choices=[("weight", "Weight"), ("volume", "Volume")], max_length=20, null=True),
        ),
        migrations.AddField(
            model_name="order",
            name="unit",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="orders", to="atms_orders.unit"),
        ),
        migrations.AddField(
            model_name="order",
            name="weight_or_volume",
            field=models.FloatField(blank=True, help_text="Supplementary weight or volume measurement for planning.", null=True),
        ),
        migrations.AlterField(
            model_name="order",
            name="total_quantity",
            field=models.FloatField(default=0),
        ),
        migrations.RunPython(seed_units_and_backfill_orders, noop_reverse),
        migrations.RemoveField(
            model_name="order",
            name="estimated_cost",
        ),
        migrations.RemoveField(
            model_name="order",
            name="estimated_volume",
        ),
        migrations.RemoveField(
            model_name="order",
            name="estimated_weight",
        ),
    ]
