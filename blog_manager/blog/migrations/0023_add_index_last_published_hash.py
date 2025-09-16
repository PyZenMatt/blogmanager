"""Add DB index to last_published_hash

Auto-generated migration to add index for faster lookup.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("blog", "0022_add_last_published_hash"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="post",
            index=models.Index(fields=["last_published_hash"], name="post_last_pub_hash_idx"),
        ),
    ]
