import os
from pathlib import Path
import pytest
from environ import Env
from core.db import build_database_config


def test_build_sqlite_config(tmp_path, monkeypatch):
    env = Env()
    monkeypatch.setenv("DB_ENGINE", "sqlite")
    monkeypatch.setenv("SQLITE_NAME", "unit.sqlite3")
    cfg = build_database_config(env, tmp_path)
    assert cfg["ENGINE"] == "django.db.backends.sqlite3"
    assert cfg["NAME"].endswith("unit.sqlite3")
    assert cfg["ATOMIC_REQUESTS"] is True


def test_build_mysql_config(monkeypatch, tmp_path):
    env = Env()
    monkeypatch.setenv("DB_ENGINE", "mysql")
    monkeypatch.setenv("DB_NAME", "x")
    monkeypatch.setenv("DB_USER", "u")
    monkeypatch.setenv("DB_PASSWORD", "p")
    monkeypatch.setenv("DB_HOST", "h")
    monkeypatch.setenv("DB_PORT", "3306")
    cfg = build_database_config(env, tmp_path)
    assert cfg["ENGINE"] == "django.db.backends.mysql"
    assert cfg["NAME"] == "x"
    assert cfg["ATOMIC_REQUESTS"] is True
