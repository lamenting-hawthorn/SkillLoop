import json
import sqlite3

from skillloop.adapters.hermes import load_hermes_state_db, normalize_hermes_export


def test_hermes_export_normalizes_messages():
    trace = normalize_hermes_export(
        {
            "session_id": "s1",
            "messages": [
                {"role": "user", "content": "fix this"},
                {"role": "assistant", "content": "done"},
            ],
        }
    )

    assert trace.source == "hermes"
    assert trace.metadata["session_id"] == "s1"
    assert trace.messages[-1].content == "done"


def test_hermes_state_db_loads_latest_session_read_only(tmp_path):
    db = tmp_path / "state.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT, title TEXT, started_at REAL, ended_at REAL, message_count INTEGER)")
    conn.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, tool_calls TEXT, timestamp REAL, active INTEGER)")
    conn.execute("INSERT INTO sessions VALUES ('old', 'cli', 'Old', 1.0, NULL, 1)")
    conn.execute("INSERT INTO sessions VALUES ('new', 'cli', 'New', 2.0, NULL, 2)")
    conn.execute("INSERT INTO messages (session_id, role, content, tool_calls, timestamp, active) VALUES ('new', 'user', 'hello', NULL, 2.1, 1)")
    conn.execute("INSERT INTO messages (session_id, role, content, tool_calls, timestamp, active) VALUES ('new', 'assistant', 'hi', ?, 2.2, 1)", (json.dumps([{"name": "terminal", "arguments": {"command": "pwd"}, "success": True}]),))
    conn.commit()
    conn.close()

    trace = load_hermes_state_db(db, latest=True)

    assert trace.source == "hermes_state_db"
    assert trace.metadata["session_id"] == "new"
    assert [m.role for m in trace.messages] == ["user", "assistant"]
    assert trace.messages[1].tool_calls[0].name == "terminal"
