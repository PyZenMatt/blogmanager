from django.db import migrations, models

def dedupe_slugs(apps, schema_editor):
    Post = apps.get_model("blog", "Post")
    # De-dup per (site, slug): assegna suffix -2, -3, ...
    from collections import defaultdict
    seen = defaultdict(set)
    for p in Post.objects.order_by("site_id", "slug", "id").only("id", "site_id", "slug", "title"):
        key = (p.site_id, p.slug or "")
        if p.slug and p.slug not in seen[p.site_id]:
            seen[p.site_id].add(p.slug)
            continue
        # genera nuovo slug unico basandosi sul titolo o slug esistente
        base = p.slug or ""
        title = p.title or ""
        slug_base = base if base else None
        import re
        import unicodedata
        from django.utils.text import slugify as dj_slugify
        def _norm(s):
            s = re.sub(r"[\x00\uD800-\uDFFF]", "", s or "")
            try:
                s = unicodedata.normalize("NFKD", s)
            except Exception:
                pass
            return s
        base_clean = dj_slugify(_norm(slug_base or title)) or "post"
        base_clean = base_clean[:200].strip("-")
        candidate = base_clean
        i = 2
        while Post.objects.filter(site_id=p.site_id, slug=candidate).exists():
            suffix = f"-{i}"
            cut = 200 - len(suffix)
            candidate = f"{base_clean[:cut].rstrip('-')}{suffix}"
            i += 1
        Post.objects.filter(pk=p.id).update(slug=candidate)

class Migration(migrations.Migration):
    dependencies = [
        ("blog", "0006_alter_post_background"),
    ]
    operations = [
        migrations.AlterField(
            model_name="post",
            name="slug",
            field=models.SlugField(max_length=200, db_collation="utf8mb4_unicode_ci"),
        ),
        migrations.RunPython(dedupe_slugs, reverse_code=migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="post",
            constraint=models.UniqueConstraint(fields=["site", "slug"], name="uniq_site_slug"),
        ),
    ]
