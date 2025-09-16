import sqlite3

import pytest

from django.db import connections


@pytest.fixture(autouse=True)
def sqlite_collation_setup():
    """Register a no-op collation named utf8mb4_unicode_ci for sqlite tests."""
    conn = connections["default"].connection
    if isinstance(conn, sqlite3.Connection):
        try:
            conn.create_collation("utf8mb4_unicode_ci", lambda a, b: (a > b) - (a < b))
        except Exception:
            # if not available or already registered, ignore
            pass
    yield