from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="maintenancelog",
            name="service_types",
            field=models.ManyToManyField(
                related_name="maintenance_logs",
                through="core.LogService",
                through_fields=("log", "service_type"),
                to="core.servicetype",
            ),
        ),
    ]
