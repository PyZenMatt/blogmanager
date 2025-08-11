from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("blog", "0010_post_editorial_workflow"),
    ]

    operations = [
        migrations.AddField(
            model_name="site",
            name="repo_owner",
            field=models.CharField(
                max_length=100, blank=True, help_text="GitHub owner/org"
            ),
        ),
        migrations.AddField(
            model_name="site",
            name="repo_name",
            field=models.CharField(
                max_length=100, blank=True, help_text="GitHub repo name"
            ),
        ),
        migrations.AddField(
            model_name="site",
            name="default_branch",
            field=models.CharField(
                max_length=100, default="main", help_text="Default branch"
            ),
        ),
        migrations.AddField(
            model_name="site",
            name="posts_dir",
            field=models.CharField(
                max_length=100, default="_posts", help_text="Directory for posts"
            ),
        ),
        migrations.AddField(
            model_name="site",
            name="media_dir",
            field=models.CharField(
                max_length=100, default="assets/img", help_text="Directory for media"
            ),
        ),
        migrations.AddField(
            model_name="site",
            name="base_url",
            field=models.URLField(blank=True, help_text="Base URL for published site"),
        ),
    ]
