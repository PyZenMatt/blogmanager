import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("blog", "0009_remove_post_alt_remove_post_og_type_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="post",
            name="status",
            field=models.CharField(
                max_length=10,
                choices=[("draft", "Draft"), ("review", "Review"), ("published", "Published")],
                default="draft",
            ),
        ),
        migrations.AddField(
            model_name="post",
            name="reviewed_by",
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="auth.user",
                related_name="reviewed_posts",
            ),
        ),
        migrations.AddField(
            model_name="post",
            name="reviewed_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="post",
            name="review_notes",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="post",
            name="published_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]
