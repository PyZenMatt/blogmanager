"""Add repo_filename field to Post.

Auto-generated during patch session.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '00xx_add_slug_locked'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='repo_filename',
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
    ]
