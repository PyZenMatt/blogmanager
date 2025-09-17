# Generated migration for ExportAudit
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("blog", "0025_remove_post_post_last_pub_hash_idx_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExportAudit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("run_id", models.CharField(max_length=64, db_index=True)),
                ("action", models.CharField(max_length=64)),
                ("summary", models.JSONField(blank=True, null=True)),
                ("created_by", models.CharField(max_length=100, blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("site", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="blog.site")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
