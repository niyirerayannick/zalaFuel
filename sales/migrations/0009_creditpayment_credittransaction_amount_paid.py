from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sales", "0008_shiftsession_shift_type"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="credittransaction",
            name="amount_paid",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.CreateModel(
            name="CreditPayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("method", models.CharField(choices=[("cash", "Cash"), ("card", "Card"), ("mobile", "Mobile Money"), ("bank", "Bank Transfer")], default="cash", max_length=20)),
                ("reference", models.CharField(blank=True, max_length=60)),
                ("notes", models.TextField(blank=True)),
                ("customer", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="credit_payments", to="sales.customer")),
                ("received_by", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name="credit_payments_received", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
