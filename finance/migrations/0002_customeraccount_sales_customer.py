from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0007_shiftsession_cash_reconciliation_fields"),
        ("finance", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="customeraccount",
            name="sales_customer",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="finance_customer_account",
                to="sales.customer",
            ),
        ),
    ]
