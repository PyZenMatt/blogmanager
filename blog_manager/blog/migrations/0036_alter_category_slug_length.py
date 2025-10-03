"""Increase slug field lengths to 200 to avoid MySQL 'Data too long' errors.

This migration alters the `slug`, `cluster_slug` and `subcluster_slug` columns on
`blog_category` to use max_length=200. It's safe for SQLite and MySQL; on MySQL
it will alter the VARCHAR length. Ensure you have a backup before applying in
production.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("blog", "0035_normalize_categories"),
    ]

    operations = [
        migrations.AlterField(
            model_name="category",
            name="slug",
            field=models.SlugField(max_length=200),
        ),
        migrations.AlterField(
            model_name="category",
            name="cluster_slug",
            field=models.SlugField(max_length=200, help_text="Normalized cluster identifier (e.g., django, frontend)"),
        ),
        migrations.AlterField(
            model_name="category",
            name="subcluster_slug",
            field=models.SlugField(max_length=200, blank=True, null=True, help_text="Optional subcluster identifier (e.g., forms, authentication)"),
        ),
    ]
