from django.db import migrations, models
from django.utils.text import slugify


def populate_slug(apps, schema_editor):
    Site = apps.get_model("blog", "Site")
    for s in Site.objects.all():
        if not getattr(s, "slug", None):
            base = slugify(s.name) or slugify(s.domain) or f"site-{s.pk}"
            slug = base
            i = 2
            while Site.objects.filter(slug=slug).exclude(pk=s.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            s.slug = slug
            s.save(update_fields=["slug"])


class Migration(migrations.Migration):
    dependencies = [
        ("blog", "0018_alter_post_created_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="site",
            name="slug",
            field=models.SlugField(blank=True, unique=True),
        ),
        migrations.AddField(
            model_name="site",
            name="repo_path",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Percorso working copy locale del repo Jekyll (se vuoto usa BLOG_REPO_BASE/<slug> se esiste)",
                max_length=255,
            ),
        ),
        migrations.RunPython(populate_slug, migrations.RunPython.noop),
    ]
