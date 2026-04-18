from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("atms_drivers", "0003_driver_assigned_vehicle_driver_availability_status_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="driver",
            name="work_status",
            field=models.CharField(
                choices=[("COMPANY", "Company Driver"), ("EXTERNAL", "External Driver")],
                default="COMPANY",
                max_length=16,
            ),
        ),
    ]
