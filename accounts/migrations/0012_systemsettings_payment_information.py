from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0011_user_session_invalid_before"),
    ]

    operations = [
        migrations.AddField(
            model_name="systemsettings",
            name="rwf_account_name",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="systemsettings",
            name="rwf_account_number",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="systemsettings",
            name="rwf_bank_name",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="systemsettings",
            name="usd_account_name",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="systemsettings",
            name="usd_account_number",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="systemsettings",
            name="usd_bank_name",
            field=models.CharField(blank=True, max_length=120),
        ),
    ]
