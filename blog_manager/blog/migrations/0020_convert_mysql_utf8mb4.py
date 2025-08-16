from django.db import migrations
from django.db import connection


def forwards(apps, schema_editor):
    """
    Idempotent migration to convert MySQL database and tables to utf8mb4_unicode_ci.
    Only runs if using MySQL backend. Safe to run multiple times.
    """
    if connection.vendor != "mysql":
        # Skip for non-MySQL databases (e.g., SQLite in tests)
        return

    UTF8 = "utf8mb4"
    COLL = "utf8mb4_unicode_ci"

    with connection.cursor() as cursor:
        # Convert database charset (if needed)
        try:
            cursor.execute(f"ALTER DATABASE `{connection.settings_dict['NAME']}` CHARACTER SET {UTF8} COLLATE {COLL}")
        except Exception:
            # Database conversion may fail due to permissions, continue with tables
            pass

        # Get all blog-related tables
        cursor.execute(
            """
            SELECT TABLE_NAME 
            FROM information_schema.TABLES 
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME LIKE 'blog_%'
        """,
            [connection.settings_dict["NAME"]],
        )

        tables = [row[0] for row in cursor.fetchall()]

        # Convert each table to utf8mb4
        for table in tables:
            try:
                cursor.execute(f"ALTER TABLE `{table}` CONVERT TO CHARACTER SET {UTF8} COLLATE {COLL}")
            except Exception:
                # Table conversion may fail, but don't stop the migration
                pass


def backwards(apps, schema_editor):
    """
    Backwards migration is intentionally a no-op since reverting charset changes
    could cause data loss for existing utf8mb4 content (emojis, etc.)
    """
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("blog", "0019_site_slug_repo_path"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
