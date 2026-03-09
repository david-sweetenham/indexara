"""Database connection management."""
from __future__ import annotations
import sqlite3
from pathlib import Path
from .schema import CATALOG_SCHEMA, SEARCH_SCHEMA


def _open_db(db_path: str, schema: str) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(schema)
    conn.commit()
    return conn


def get_catalog_conn(catalog_db_path: str) -> sqlite3.Connection:
    return _open_db(catalog_db_path, CATALOG_SCHEMA)


def get_search_conn(search_db_path: str) -> sqlite3.Connection:
    return _open_db(search_db_path, SEARCH_SCHEMA)
