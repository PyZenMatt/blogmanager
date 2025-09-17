# Migration for MigrationLog
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("blog", "0026_add_exportaudit"),
    ]

    operations = [
        migrations.CreateModel(
            name="MigrationLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("run_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.CharField(max_length=150, blank=True, null=True)),
                ("command", models.CharField(max_length=200)),
                ("output", models.TextField(blank=True, null=True)),
                ("success", models.BooleanField(default=False)),
            ],
            options={
                "ordering": ["-run_at"],
            },
        ),
    ]
