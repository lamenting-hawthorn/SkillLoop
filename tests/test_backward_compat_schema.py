import json
import sqlite3

from skillloop.infrastructure.sqlite.migrations import apply_migrations, current_schema_version


def test_migrate_v1_to_v2(tmp_path):
    """Create a v1 database fixture and ensure migration to v2 succeeds."""
    db_path = tmp_path / "skillloop.db"

    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE traces ("
        "id TEXT PRIMARY KEY, source TEXT NOT NULL, "
        "created_at TEXT NOT NULL, payload TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE evaluations ("
        "id TEXT PRIMARY KEY, trace_id TEXT NOT NULL, "
        "score INTEGER NOT NULL, created_at TEXT NOT NULL, "
        "payload TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE proposals ("
        "id TEXT PRIMARY KEY, trace_id TEXT NOT NULL, "
        "kind TEXT NOT NULL, status TEXT NOT NULL, "
        "created_at TEXT NOT NULL, payload TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE controller_runs ("
        "id TEXT PRIMARY KEY, started_at TEXT NOT NULL, "
        "finished_at TEXT, payload TEXT NOT NULL)"
    )
    conn.execute("PRAGMA user_version = 1")

    proposal_payload = json.dumps(
        {
            "id": "p1",
            "trace_id": "t1",
            "kind": "memory",
            "title": "Remember concise answers",
            "content": "User prefers concise answers.",
            "reason": "user feedback",
            "status": "pending",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    )
    conn.execute(
        "INSERT INTO proposals(id, trace_id, kind, status, created_at, payload) "
        "VALUES ('p1', 't1', 'memory', 'pending', '2026-01-01T00:00:00+00:00', ?)",
        (proposal_payload,),
    )
    conn.commit()
    conn.close()

    conn = sqlite3.connect(str(db_path))
    assert current_schema_version(conn) == 1

    final_version = apply_migrations(conn, target=2)
    assert final_version == 2
    assert current_schema_version(conn) == 2

    columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(proposals)")}
    assert "content_hash" in columns

    proposal_row = conn.execute("SELECT content_hash FROM proposals WHERE id = 'p1'").fetchone()
    assert proposal_row is not None
    assert proposal_row[0] is not None
    assert len(proposal_row[0]) == 64

    conn.close()
