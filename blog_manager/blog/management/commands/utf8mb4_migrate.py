from django.core.management.base import BaseCommand, CommandError
from django.db import connections


class Command(BaseCommand):
    help = (
        "Generate (or execute with --execute) ALTER TABLE statements to convert blog_* tables "
        "to utf8mb4 + utf8mb4_unicode_ci. Dry-run by default."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Actually run the ALTER TABLE statements (default: dry-run)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Skip interactive confirmation when --execute is given",
        )

    def handle(self, *args, **options):
        conn = connections["default"]
        with conn.cursor() as cur:
            cur.execute(
                "SELECT TABLE_NAME FROM information_schema.tables WHERE table_schema = DATABASE() AND TABLE_NAME LIKE 'blog_%'"
            )
            rows = [r[0] for r in cur.fetchall()]

        if not rows:
            self.stdout.write("No tables found matching blog_%")
            return

        statements = [
            f"ALTER TABLE `{t}` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            for t in rows
        ]

        self.stdout.write("Found tables:")
        for t in rows:
            self.stdout.write("  - %s" % t)

        self.stdout.write("\nGenerated statements:\n")
        for s in statements:
            self.stdout.write(s)

        if not options["execute"]:
            self.stdout.write("\nDry-run mode. Re-run with --execute to apply the statements.")
            return

        if not options["force"]:
            confirm = input("Type 'yes' to confirm running ALTER TABLE on the above tables: ")
            if confirm.strip().lower() != "yes":
                raise CommandError("Aborted by user")

        had_error = False
        for s, t in zip(statements, rows):
            self.stdout.write(f"Running: {s}")
            try:
                with conn.cursor() as cur:
                    cur.execute(s)
                self.stdout.write(self.style.SUCCESS(f"OK: {t}"))
            except Exception as e:
                had_error = True
                self.stdout.write(self.style.ERROR(f"Failed on {t}: {e}"))

        if had_error:
            raise CommandError("One or more ALTER TABLE statements failed; review output")
        self.stdout.write(self.style.SUCCESS("All tables converted successfully"))
