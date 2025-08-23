from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("blog", "0019_site_slug_repo_path"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="post",
            name="meta_title",
        ),
        migrations.RemoveField(
            model_name="post",
            name="meta_description",
        ),
        migrations.RemoveField(
            model_name="post",
            name="meta_keywords",
        ),
        migrations.RemoveField(
            model_name="post",
            name="og_title",
        ),
        migrations.RemoveField(
            model_name="post",
            name="og_description",
        ),
        migrations.RemoveField(
            model_name="post",
            name="og_image_url",
        ),
        migrations.RemoveField(
            model_name="post",
            name="noindex",
        ),
    ]
