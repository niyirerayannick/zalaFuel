from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0013_user_assigned_station_user_staff_id_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="systemsettings",
            name="diesel_unit_price",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Default POS unit price per liter for diesel",
                max_digits=12,
            ),
        ),
        migrations.AddField(
            model_name="systemsettings",
            name="petrol_unit_price",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Default POS unit price per liter for petrol",
                max_digits=12,
            ),
        ),
    ]
