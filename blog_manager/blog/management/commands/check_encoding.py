import re
import unicodedata

from django.core.management.base import BaseCommand
from django.db import connection

SUSPECT_CHARS = {"\ufffd", "\u0000"}


def is_suspect(text: str) -> bool:
    """Check if text contains suspicious characters that may indicate encoding issues."""
    if text is None:
        return False

    # Check for replacement character and null bytes
    if any(c in text for c in SUSPECT_CHARS):
        return True

    # Check for UTF-16 surrogates (should not appear in UTF-8)
    return any(0xD800 <= ord(c) <= 0xDFFF for c in text)


def normalize_text(text: str) -> str:
    """Attempt to normalize text by removing problematic characters."""
    if not text:
        return text

    # Remove null bytes and replacement characters
    cleaned = re.sub(r"[\x00\uFFFD]", "", text)

    # Remove UTF-16 surrogates
    cleaned = re.sub(r"[\uD800-\uDFFF]", "", cleaned)

    # Normalize Unicode
    try:
        cleaned = unicodedata.normalize("NFKD", cleaned)
    except Exception:
        # If normalization fails, just return the cleaned version
        pass

    return cleaned


class Command(BaseCommand):
    help = "Check and optionally fix encoding issues in blog content (dry-run by default)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually apply the fixes (default: dry-run mode)",
        )
        parser.add_argument(
            "--table",
            type=str,
            help="Specific table to check (e.g., 'blog_post')",
        )

    def handle(self, *args, **options):
        if connection.vendor != "mysql":
            self.stdout.write(
                "Note: Running on non-MySQL database, limited encoding checks available"
            )

        apply_fixes = options.get("apply", False)
        target_table = options.get("table")

        if apply_fixes:
            self.stdout.write(self.style.WARNING("APPLY MODE: Will modify database content"))
        else:
            self.stdout.write("DRY-RUN MODE: No changes will be made")

        # Get tables to check
        with connection.cursor() as cursor:
            if target_table:
                tables = [target_table]
            else:
                if connection.vendor == "mysql":
                    cursor.execute(
                        """
                        SELECT TABLE_NAME
                        FROM information_schema.TABLES
                        WHERE TABLE_SCHEMA = %s AND TABLE_NAME LIKE 'blog_%'
                    """,
                        [connection.settings_dict["NAME"]],
                    )
                    tables = [row[0] for row in cursor.fetchall()]
                else:
                    # For SQLite, get table names differently
                    cursor.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'blog_%'"
                    )
                    tables = [row[0] for row in cursor.fetchall()]

        if not tables:
            self.stdout.write("No tables found to check")
            return

        total_issues = 0

        for table_name in tables:
            self.stdout.write(f"\nChecking table: {table_name}")
            issues_found = self._check_table(table_name, apply_fixes)
            total_issues += issues_found

        self.stdout.write("\n=== SUMMARY ===")
        self.stdout.write(f"Total suspicious entries found: {total_issues}")

        if total_issues > 0:
            if apply_fixes:
                self.stdout.write(self.style.SUCCESS("Issues have been fixed"))
            else:
                self.stdout.write(self.style.WARNING("Re-run with --apply to fix issues"))
        else:
            self.stdout.write(self.style.SUCCESS("No encoding issues detected"))

    def _check_table(self, table_name, apply_fixes):
        """Check a specific table for encoding issues."""
        issues_count = 0

        with connection.cursor() as cursor:
            # Get text columns for this table
            if connection.vendor == "mysql":
                cursor.execute(
                    """
                    SELECT COLUMN_NAME
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                    AND DATA_TYPE IN ('varchar', 'text', 'longtext', 'mediumtext')
                """,
                    [connection.settings_dict["NAME"], table_name],
                )
                text_columns = [row[0] for row in cursor.fetchall()]
                id_column = "id"
            else:
                # For SQLite, use PRAGMA to get table info
                cursor.execute(f"PRAGMA table_info({table_name})")
                table_info = cursor.fetchall()
                text_columns = [
                    row[1]
                    for row in table_info
                    if "text" in row[2].lower() or "varchar" in row[2].lower()
                ]
                id_column = "rowid"

            if not text_columns:
                return 0

            # Check each row for suspicious content
            columns_sql = f"SELECT {id_column}, {', '.join(text_columns)} FROM {table_name}"
            cursor.execute(columns_sql)
            rows = cursor.fetchall()

            for row in rows:
                row_id = row[0]
                row_data = row[1:]

                for i, (column_name, value) in enumerate(zip(text_columns, row_data)):
                    if value and is_suspect(str(value)):
                        issues_count += 1
                        self.stdout.write(
                            f"  SUSPECT: {table_name}.{column_name} (id={row_id}): "
                            f"'{str(value)[:50]}...'"
                            if len(str(value)) > 50
                            else f"'{value}'"
                        )

                        if apply_fixes:
                            normalized = normalize_text(str(value))
                            if connection.vendor == "mysql":
                                cursor.execute(
                                    f"UPDATE {table_name} SET {column_name} = %s WHERE id = %s",
                                    [normalized, row_id],
                                )
                            else:
                                cursor.execute(
                                    f"UPDATE {table_name} SET {column_name} = ? WHERE rowid = ?",
                                    [normalized, row_id],
                                )
                            self.stdout.write(f"    FIXED: Updated to '{normalized[:50]}...'")

        return issues_count
