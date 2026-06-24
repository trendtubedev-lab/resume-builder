"""SQLite persistence layer for TailorCV.

DB lives at data/tailorcv.db (auto-created). All access is synchronous;
the app is single-process so no connection pooling is needed.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
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
        con.execute("""
            CREATE TABLE IF NOT EXISTS results (
                job_id      TEXT PRIMARY KEY,
                owner       TEXT NOT NULL,
                resume_json TEXT NOT NULL,
                created_at  TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS completion_cache (
                cache_key  TEXT PRIMARY KEY,
                result     TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)


# ---------------------------------------------------------------------------
# tailored results (replaces the old in-memory _STORE)
# ---------------------------------------------------------------------------

def save_result(job_id: str, owner: str, resume: dict) -> None:
    """Persist a generated resume. resume is JSON-serialized into one column."""
    with _connect() as con:
        con.execute(
            "INSERT OR REPLACE INTO results (job_id, owner, resume_json, created_at) "
            "VALUES (?, ?, ?, ?)",
            (job_id, owner, json.dumps(resume), datetime.now(timezone.utc).isoformat()),
        )


def get_result(job_id: str) -> dict | None:
    """Return {'resume': dict, 'owner': str} for a job, or None if absent."""
    with _connect() as con:
        row = con.execute(
            "SELECT owner, resume_json FROM results WHERE job_id = ?",
            (job_id,),
        ).fetchone()
    if row is None:
        return None
    return {"resume": json.loads(row["resume_json"]), "owner": row["owner"]}


# ---------------------------------------------------------------------------
# completion cache (dedup identical model calls — saves a full AI round-trip)
# ---------------------------------------------------------------------------

def get_cached_completion(cache_key: str) -> str | None:
    """Return a previously stored model result for this key, or None."""
    with _connect() as con:
        row = con.execute(
            "SELECT result FROM completion_cache WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()
    return row["result"] if row else None


def save_cached_completion(cache_key: str, result: str) -> None:
    """Store a model result keyed by a hash of (model, system, user)."""
    with _connect() as con:
        con.execute(
            "INSERT OR REPLACE INTO completion_cache (cache_key, result, created_at) "
            "VALUES (?, ?, ?)",
            (cache_key, result, datetime.now(timezone.utc).isoformat()),
        )


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
