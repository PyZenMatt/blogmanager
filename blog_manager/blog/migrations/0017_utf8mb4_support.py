# Generated migration for UTF8MB4 support to fix emoji/Unicode issues
from django.db import migrations

UTF8MB4_DB = """
ALTER DATABASE %(db)s CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;
"""

UTF8MB4_TABLES = [
    # Main tables that store user content with text fields
    "blog_post",
    "blog_author", 
    "blog_category",
    "blog_comment",
    "blog_postimage",
    "blog_tag",
    # Add other tables as needed
]


def forwards(apps, schema_editor):
    connection = schema_editor.connection
    vendor = connection.vendor
    if vendor != "mysql":
        # Only apply to MySQL databases
        return
    
    dbname = connection.settings_dict.get("NAME")
    with connection.cursor() as cursor:
        # Convert database charset
        cursor.execute(UTF8MB4_DB % {"db": dbname})
        
        # Convert tables to utf8mb4
        for table in UTF8MB4_TABLES:
            try:
                cursor.execute(f"ALTER TABLE {table} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            except Exception:
                # Table might not exist yet, continue
                pass


def backwards(apps, schema_editor):
    # No-op: avoid downgrade charset (risk of data loss)
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("blog", "0016_post_publish_audit"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]