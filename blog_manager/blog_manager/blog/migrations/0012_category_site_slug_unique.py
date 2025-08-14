# Generated migration for Category unique_together(site, slug)
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("blog", "0011_site_repo_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="category",
            name="slug",
            field=models.SlugField(),
        ),
        migrations.AlterUniqueTogether(
            name="category",
            unique_together={("site", "slug")},
        ),
        migrations.AddIndex(
            model_name="category",
            index=models.Index(
                fields=["site", "slug"], name="blog_category_site_slug_idx"
            ),
        ),
    ]
