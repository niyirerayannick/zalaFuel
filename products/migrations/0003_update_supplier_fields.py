from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0002_update_product_fields"),
    ]

    operations = [
        migrations.RenameField(model_name="supplier", old_name="name", new_name="supplier_name"),
        migrations.AddField(
            model_name="supplier",
            name="supplier_code",
            field=models.CharField(max_length=30, unique=True, verbose_name="Supplier Code"),
        ),
        migrations.AddField(
            model_name="supplier",
            name="address",
            field=models.TextField(blank=True, verbose_name="Address"),
        ),
        migrations.AddField(
            model_name="supplier",
            name="country",
            field=models.CharField(blank=True, max_length=100, verbose_name="Country"),
        ),
        migrations.AddField(
            model_name="supplier",
            name="status",
            field=models.CharField(
                choices=[("active", "Active"), ("inactive", "Inactive")],
                default="active",
                max_length=10,
                verbose_name="Status",
            ),
        ),
    ]
