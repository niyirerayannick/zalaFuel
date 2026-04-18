from decimal import Decimal
import re
from django.db import migrations, models


def backfill_total_quantity(apps, schema_editor):
    Order = apps.get_model("atms_orders", "Order")
    for order in Order.objects.all():
        total_quantity = getattr(order, "estimated_weight", None)
        if not total_quantity:
            quantity_text = getattr(order, "quantity", "") or ""
            match = re.search(r"[-+]?\d*\.?\d+", quantity_text)
            if match:
                try:
                    total_quantity = Decimal(match.group())
                except Exception:
                    total_quantity = Decimal("0")
            else:
                total_quantity = Decimal("0")
        Order.objects.filter(pk=order.pk).update(total_quantity=total_quantity)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("atms_orders", "0003_order_cargo_category"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="total_quantity",
            field=models.DecimalField(
                decimal_places=2, default=Decimal("0.00"), max_digits=12
            ),
        ),
        migrations.RunPython(backfill_total_quantity, noop_reverse),
    ]
