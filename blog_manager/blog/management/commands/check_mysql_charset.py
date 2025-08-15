from django.core.management.base import BaseCommand
from django.db import connections


class Command(BaseCommand):
    help = "Check MySQL connection character set and collation for the default DB"

    def handle(self, *args, **options):
        conn = connections['default']
        with conn.cursor() as cur:
            cur.execute("SELECT @@character_set_client, @@character_set_connection, @@character_set_database, @@collation_connection, @@collation_database")
            row = cur.fetchone()
            self.stdout.write("character_set_client: %s" % row[0])
            self.stdout.write("character_set_connection: %s" % row[1])
            self.stdout.write("character_set_database: %s" % row[2])
            self.stdout.write("collation_connection: %s" % row[3])
            self.stdout.write("collation_database: %s" % row[4])
