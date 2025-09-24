"""Add slug_locked field to Post and backfill for published posts.

Generated manually by patching models.
"""
from django.db import migrations, models


def backfill_slug_locked(apps, schema_editor):
    Post = apps.get_model('blog', 'Post')
    Post.objects.filter(status='published').update(slug_locked=True)


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0034_remove_author_blog_author_site_id_5d1f1f_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='slug_locked',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(backfill_slug_locked, reverse_code=migrations.RunPython.noop),
    ]