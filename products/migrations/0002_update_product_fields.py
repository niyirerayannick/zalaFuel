from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(model_name="product", old_name="name", new_name="product_name"),
        migrations.RenameField(model_name="product", old_name="code", new_name="product_code"),
        migrations.RenameField(model_name="product", old_name="category", new_name="product_type"),
        migrations.RenameField(model_name="product", old_name="unit", new_name="unit_of_measure"),
        migrations.RemoveField(model_name="product", name="default_price"),
        migrations.RemoveField(model_name="product", name="is_active"),
        migrations.AddField(
            model_name="product",
            name="description",
            field=models.TextField(blank=True, verbose_name="Description"),
        ),
        migrations.AddField(
            model_name="product",
            name="status",
            field=models.CharField(
                choices=[("active", "Active"), ("inactive", "Inactive")],
                default="active",
                max_length=10,
                verbose_name="Status",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="density",
            field=models.DecimalField(
                blank=True, decimal_places=3, max_digits=6, null=True, verbose_name="Density (kg/m³)"
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="temperature_factor",
            field=models.DecimalField(
                blank=True, decimal_places=6, max_digits=8, null=True, verbose_name="Temperature Factor"
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="color_marker",
            field=models.CharField(blank=True, max_length=20, verbose_name="Color Marker"),
        ),
        migrations.AddField(
            model_name="product",
            name="display_order",
            field=models.PositiveIntegerField(default=0, verbose_name="Display Order"),
        ),
        migrations.AlterField(
            model_name="product",
            name="product_type",
            field=models.CharField(
                choices=[
                    ("pms", "Premium Motor Spirit (PMS)"),
                    ("ago", "Automotive Gas Oil (AGO)"),
                    ("dpk", "Dual Purpose Kerosene (DPK)"),
                    ("lpg", "Liquefied Petroleum Gas (LPG)"),
                    ("other", "Other"),
                ],
                default="pms",
                max_length=20,
                verbose_name="Product Type",
            ),
        ),
        migrations.AlterField(
            model_name="product",
            name="product_code",
            field=models.CharField(max_length=30, unique=True, verbose_name="Product Code"),
        ),
        migrations.AlterField(
            model_name="product",
            name="product_name",
            field=models.CharField(max_length=120, unique=True, verbose_name="Product Name"),
        ),
        migrations.AlterField(
            model_name="product",
            name="unit_of_measure",
            field=models.CharField(default="Liters", max_length=20, verbose_name="Unit of Measure"),
        ),
    ]