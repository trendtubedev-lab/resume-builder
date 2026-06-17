"""SQLite persistence layer for TailorCV.

DB lives at data/tailorcv.db (auto-created). All access is synchronous;
the app is single-process so no connection pooling is needed.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

_DB_PATH = Path(__file__).parent.parent / "data" / "tailorcv.db"


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(_DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_db() -> None:
    """Create tables if they don't exist. Safe to call at every startup."""
    with _connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS custom_personas (
                key        TEXT NOT NULL,
                user_email TEXT NOT NULL,
                name       TEXT NOT NULL,
                brief      TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (key, user_email)
            )
        """)


# ---------------------------------------------------------------------------
# custom_personas CRUD
# ---------------------------------------------------------------------------

def list_custom_personas(user_email: str) -> list[dict]:
    with _connect() as con:
        rows = con.execute(
            "SELECT key, name, brief, sort_order FROM custom_personas "
            "WHERE user_email = ? ORDER BY sort_order, key",
            (user_email,),
        ).fetchall()
    return [dict(r) for r in rows]


def upsert_persona(user_email: str, key: str, name: str, brief: str, sort_order: int = 0) -> None:
    with _connect() as con:
        con.execute(
            """INSERT INTO custom_personas (key, user_email, name, brief, sort_order)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(key, user_email) DO UPDATE SET
                   name=excluded.name,
                   brief=excluded.brief,
                   sort_order=excluded.sort_order""",
            (key, user_email, name, brief, sort_order),
        )


def delete_persona(user_email: str, key: str) -> bool:
    """Delete a custom persona. Returns True if a row was removed."""
    with _connect() as con:
        cur = con.execute(
            "DELETE FROM custom_personas WHERE key = ? AND user_email = ?",
            (key, user_email),
        )
    return cur.rowcount > 0
