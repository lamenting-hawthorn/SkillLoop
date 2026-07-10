from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable

from skillloop.schema import SCHEMA_VERSION, Proposal

MigrationFn = Callable[[sqlite3.Connection], None]


class Migration:
    def __init__(self, version: int, name: str, apply: MigrationFn) -> None:
        self.version = version
        self.name = name
        self.apply = apply


def _create_initial_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS traces (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            created_at TEXT NOT NULL,
            payload TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS evaluations (
            id TEXT PRIMARY KEY,
            trace_id TEXT NOT NULL,
            score INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            payload TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS proposals (
            id TEXT PRIMARY KEY,
            trace_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            payload TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS controller_runs (
            id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            payload TEXT NOT NULL
        )
        """
    )


def _upgrade_proposals_to_v2(conn: sqlite3.Connection) -> None:
    columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(proposals)")}
    if "content_hash" not in columns:
        conn.execute("ALTER TABLE proposals ADD COLUMN content_hash TEXT")
    for proposal_id, payload in conn.execute(
        "SELECT id, payload FROM proposals WHERE content_hash IS NULL"
    ).fetchall():
        try:
            content_hash = Proposal.from_dict(json.loads(payload)).content_hash
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        conn.execute(
            "UPDATE proposals SET content_hash = ? WHERE id = ?",
            (content_hash, proposal_id),
        )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_evaluations_trace_created ON evaluations(trace_id, created_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_proposals_status_created ON proposals(status, created_at DESC)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_proposals_content_hash ON proposals(content_hash)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_controller_runs_started ON controller_runs(started_at DESC)"
    )


MIGRATIONS: list[Migration] = [
    Migration(version=1, name="create_initial_tables", apply=_create_initial_tables),
    Migration(version=2, name="proposals_content_hash_and_indexes", apply=_upgrade_proposals_to_v2),
]


def current_schema_version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def apply_migrations(conn: sqlite3.Connection, target: int | None = None) -> int:
    """Apply all pending migrations atomically, one transaction per migration.

    Returns the resulting schema version. Idempotent: each migration uses
    IF NOT EXISTS / guarded ALTER so re-running on an already-migrated DB is safe.
    """
    target = target if target is not None else SCHEMA_VERSION
    version = current_schema_version(conn)
    for migration in sorted(MIGRATIONS, key=lambda m: m.version):
        if migration.version <= version:
            continue
        if migration.version > target:
            break
        with conn:
            migration.apply(conn)
            conn.execute(f"PRAGMA user_version = {migration.version}")
        version = migration.version
    return version
