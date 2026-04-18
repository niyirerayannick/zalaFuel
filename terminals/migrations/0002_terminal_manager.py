from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0013_user_assigned_station_user_staff_id_and_more"),
        ("terminals", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="terminal",
            name="manager",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="managed_terminals",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
