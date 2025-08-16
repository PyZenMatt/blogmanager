import os
from pathlib import Path
import pytest
from environ import Env
from core.db import build_database_config


def test_build_sqlite_config(tmp_path, monkeypatch):
    env = Env()
    monkeypatch.setenv("DB_ENGINE", "sqlite")
    monkeypatch.setenv("SQLITE_NAME", "unit.sqlite3")
    monkeypatch.setenv("CONN_MAX_AGE", "25")
    cfg = build_database_config(env, tmp_path)
    assert cfg["ENGINE"] == "django.db.backends.sqlite3"
    assert cfg["NAME"].endswith("unit.sqlite3")
    assert cfg["CONN_MAX_AGE"] == 25
    assert cfg["ATOMIC_REQUESTS"] is True


def test_build_mysql_config(monkeypatch, tmp_path):
    env = Env()
    monkeypatch.setenv("DB_ENGINE", "mysql")
    monkeypatch.setenv("DB_NAME", "x")
    monkeypatch.setenv("DB_USER", "u")
    monkeypatch.setenv("DB_PASSWORD", "p")
    monkeypatch.setenv("DB_HOST", "h")
    monkeypatch.setenv("DB_PORT", "3306")
    monkeypatch.setenv("CONN_MAX_AGE", "120")
    cfg = build_database_config(env, tmp_path)
    assert cfg["ENGINE"] == "django.db.backends.mysql"
    assert cfg["NAME"] == "x"
    assert cfg["CONN_MAX_AGE"] == 120
    assert cfg["ATOMIC_REQUESTS"] is True


def test_conn_max_age_defaults(monkeypatch, tmp_path):
    """Test that CONN_MAX_AGE defaults work correctly."""
    env = Env()
    
    # Clear any existing CONN_MAX_AGE setting
    monkeypatch.delenv("CONN_MAX_AGE", raising=False)
    
    # Test SQLite default (0)
    monkeypatch.setenv("DB_ENGINE", "sqlite")
    monkeypatch.setenv("SQLITE_NAME", "default.sqlite3")
    cfg = build_database_config(env, tmp_path)
    assert cfg["CONN_MAX_AGE"] == 0
    
    # Test MySQL default (60)
    monkeypatch.setenv("DB_ENGINE", "mysql")
    monkeypatch.setenv("DB_NAME", "test")
    monkeypatch.setenv("DB_USER", "test")
    monkeypatch.setenv("DB_PASSWORD", "test")
    cfg = build_database_config(env, tmp_path)
    assert cfg["CONN_MAX_AGE"] == 60
