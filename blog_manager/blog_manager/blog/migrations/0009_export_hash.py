from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ("blog", "0008_site_slug_unique"),
    ]
    operations = [
        migrations.AddField(
            model_name="post",
            name="exported_hash",
            field=models.CharField(max_length=64, blank=True, default=""),
        ),
        migrations.AddField(
            model_name="post",
            name="last_exported_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]
