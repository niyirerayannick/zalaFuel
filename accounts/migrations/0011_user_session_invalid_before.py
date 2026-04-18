from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0010_user_must_change_password"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="session_invalid_before",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
