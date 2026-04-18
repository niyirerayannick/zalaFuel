from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sales", "0007_shiftsession_cash_reconciliation_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="shiftsession",
            name="shift_type",
            field=models.CharField(
                choices=[
                    ("morning", "Morning Shift"),
                    ("evening", "Evening Shift"),
                    ("night", "Night Shift"),
                ],
                default="morning",
                max_length=20,
            ),
        ),
    ]
