from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("blog", "0015_post_meta_description_post_meta_keywords_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="post",
            name="exported_at",
            field=models.DateTimeField(
                blank=True, null=True, help_text="Timestamp dell'ultima esportazione"
            ),
        ),
        migrations.AddField(
            model_name="post",
            name="last_commit_sha",
            field=models.CharField(
                blank=True,
                max_length=64,
                null=True,
                help_text="SHA dell'ultimo commit di pubblicazione",
            ),
        ),
        migrations.AddField(
            model_name="post",
            name="repo_path",
            field=models.CharField(
                blank=True,
                max_length=255,
                null=True,
                help_text="Percorso del file nel repo Jekyll (_posts/....md)",
            ),
        ),
    ]
