from django.db import migrations, models


def backfill_weight_kg(apps, schema_editor):
    Order = apps.get_model("atms_orders", "Order")
    Unit = apps.get_model("atms_orders", "Unit")

    units_by_id = {unit.pk: unit for unit in Unit.objects.all()}

    for order in Order.objects.all():
        weight_kg = None
        if getattr(order, "measurement_type", None) == "weight" and getattr(order, "weight_or_volume", None):
            unit = units_by_id.get(order.unit_id)
            value = float(order.weight_or_volume or 0)
            if unit and unit.symbol == "ton":
                weight_kg = value * 1000
            elif unit and unit.symbol == "kg":
                weight_kg = value
            else:
                weight_kg = value
        elif getattr(order, "weight_or_volume", None) and getattr(order, "unit_id", None):
            unit = units_by_id.get(order.unit_id)
            if unit and unit.measurement_category == "weight":
                value = float(order.weight_or_volume or 0)
                weight_kg = value * 1000 if unit.symbol == "ton" else value
        elif getattr(order, "unit_id", None):
            unit = units_by_id.get(order.unit_id)
            quantity = float(order.total_quantity or 0)
            if unit and unit.symbol == "ton":
                weight_kg = quantity * 1000
            elif unit and unit.symbol == "kg":
                weight_kg = quantity

        Order.objects.filter(pk=order.pk).update(weight_kg=weight_kg)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("atms_orders", "0007_order_units_and_currency_cleanup"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="weight_kg",
            field=models.FloatField(blank=True, help_text="Total cargo weight in kilograms.", null=True),
        ),
        migrations.RunPython(backfill_weight_kg, noop_reverse),
        migrations.RemoveField(
            model_name="order",
            name="measurement_type",
        ),
        migrations.RemoveField(
            model_name="order",
            name="weight_or_volume",
        ),
        migrations.AlterField(
            model_name="order",
            name="total_quantity",
            field=models.FloatField(),
        ),
    ]
