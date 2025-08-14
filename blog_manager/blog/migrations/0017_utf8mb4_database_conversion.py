# Generated manually for utf8mb4 database and table conversion
from django.db import migrations

UTF8MB4_DB = """
ALTER DATABASE %(db)s CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;
"""

UTF8MB4_TABLES = [
    # Main blog tables that contain user text
    "blog_post",
    "blog_site", 
    "blog_category",
    "blog_author",
    "blog_comment",
    "blog_tag",
    "contact_contactmessage",
]

def forwards(apps, schema_editor):
    connection = schema_editor.connection
    vendor = connection.vendor
    if vendor != "mysql":
        return
    dbname = connection.settings_dict.get("NAME")
    with connection.cursor() as cursor:
        cursor.execute(UTF8MB4_DB % {"db": dbname})
        for table in UTF8MB4_TABLES:
            cursor.execute(f"ALTER TABLE {table} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")

def backwards(apps, schema_editor):
    # No-op: evitare downgrade charset (rischio dati)
    pass

class Migration(migrations.Migration):
    dependencies = [
        ("blog", "0016_post_publish_audit"),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]