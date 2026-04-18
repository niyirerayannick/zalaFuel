from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0006_fuelsale_inventory_posted_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="shiftsession",
            name="expected_cash",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="shiftsession",
            name="closing_card_total",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="shiftsession",
            name="closing_mobile_total",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="shiftsession",
            name="closing_credit_total",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AlterField(
            model_name="shiftsession",
            name="variance_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Cash variance: declared closing cash minus expected cash from cash sales.",
                max_digits=12,
            ),
        ),
    ]
