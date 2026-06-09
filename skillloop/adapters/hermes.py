from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from skillloop.sanitize import redact_secrets
from skillloop.schema import AgentMessage, AgentTrace, ToolCall, sha256_text, stable_json_dumps

ADAPTER_NAME = "hermes"
ADAPTER_VERSION = "1.1"


def normalize_hermes_export(data: dict[str, Any]) -> AgentTrace:
    raw_messages = data.get("messages") or data.get("conversation") or []
    messages: list[AgentMessage] = []
    for item in raw_messages:
        role = str(item.get("role", "user"))
        if role not in {"system", "user", "assistant", "tool"}:
            role = "assistant" if role == "agent" else "user"
        tool_calls = []
        for call in item.get("tool_calls", []) or []:
            tool_calls.append(
                ToolCall(
                    name=str(call.get("name") or call.get("function", {}).get("name") or "unknown"),
                    arguments=dict(call.get("arguments") or call.get("function", {}).get("arguments") or {}),
                    result=call.get("result"),
                    success=call.get("success"),
                    id=str(call.get("id") or call.get("tool_call_id") or ""),
                    started_at=call.get("started_at"),
                    ended_at=call.get("ended_at"),
                    duration_ms=call.get("duration_ms"),
                    exit_code=call.get("exit_code"),
                    status=call.get("status"),
                    error_type=call.get("error_type"),
                    artifact_refs=call.get("artifact_refs") or [],
                )
            )
        messages.append(
            AgentMessage(
                role=role,
                content=redact_secrets(str(item.get("content") or item.get("text") or "")),
                tool_calls=tool_calls,
                metadata={k: v for k, v in item.items() if k not in {"role", "content", "text", "tool_calls"}},
            )
        )
    return AgentTrace(
        source="hermes",
        messages=messages,
        adapter={"name": ADAPTER_NAME, "version": ADAPTER_VERSION},
        runtime={"name": str(data.get("runtime") or data.get("provider") or "hermes")},
        metadata={"session_id": data.get("session_id") or data.get("id"), "raw_keys": sorted(data.keys())},
        raw_trace_sha256=sha256_text(stable_json_dumps(data)),
    )


def load_hermes_export(path: str | Path) -> AgentTrace:
    source_path = Path(path)
    raw_text = source_path.read_text()
    trace = normalize_hermes_export(json.loads(raw_text))
    trace.raw_artifact_ref = str(source_path)
    trace.raw_trace_sha256 = sha256_text(raw_text)
    return trace


def _parse_tool_calls(raw: str | None) -> list[ToolCall]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    calls: list[ToolCall] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        raw_function = item.get("function")
        function: dict[str, Any] = raw_function if isinstance(raw_function, dict) else {}
        arguments = item.get("arguments") or function.get("arguments") or {}
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {"raw": arguments}
        calls.append(
            ToolCall(
                name=str(item.get("name") or function.get("name") or "unknown"),
                arguments=dict(arguments or {}),
                result=item.get("result"),
                success=item.get("success"),
                id=str(item.get("id") or item.get("tool_call_id") or ""),
                started_at=item.get("started_at"),
                ended_at=item.get("ended_at"),
                duration_ms=item.get("duration_ms"),
                exit_code=item.get("exit_code"),
                status=item.get("status"),
                error_type=item.get("error_type"),
                artifact_refs=item.get("artifact_refs") or [],
            )
        )
    return calls


def _latest_session_id(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        """
        SELECT id FROM sessions
        WHERE COALESCE(message_count, 0) > 0
        ORDER BY COALESCE(ended_at, started_at, 0) DESC, started_at DESC
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        raise ValueError("No Hermes sessions with messages found in state database")
    return str(row[0])


def load_hermes_state_db(db_path: str | Path, session_id: str | None = None, latest: bool = False) -> AgentTrace:
    """Load a Hermes session from `state.db` without mutating the database.

    The connection uses SQLite read-only URI mode. Callers must pass either an
    explicit `session_id` or `latest=True`.
    """
    path = Path(db_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    uri = f"file:{path}?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        selected_session_id = _latest_session_id(conn) if latest else session_id
        if not selected_session_id:
            raise ValueError("Pass session_id or latest=True")
        session_row = conn.execute(
            "SELECT id, source, title, started_at, ended_at FROM sessions WHERE id = ?",
            (selected_session_id,),
        ).fetchone()
        if session_row is None:
            raise KeyError(f"Hermes session not found: {selected_session_id}")
        message_rows = conn.execute(
            """
            SELECT role, content, tool_calls, timestamp, id
            FROM messages
            WHERE session_id = ? AND COALESCE(active, 1) = 1
            ORDER BY timestamp ASC, id ASC
            """,
            (selected_session_id,),
        ).fetchall()

    messages = [
        AgentMessage(
            role=role if role in {"system", "user", "assistant", "tool"} else "assistant",
            content=redact_secrets(content or ""),
            tool_calls=_parse_tool_calls(tool_calls),
            metadata={"timestamp": timestamp, "message_id": message_id},
        )
        for role, content, tool_calls, timestamp, message_id in message_rows
        if role in {"system", "user", "assistant", "tool"} and (content or tool_calls)
    ]
    return AgentTrace(
        source="hermes_state_db",
        messages=messages,
        adapter={"name": "hermes_state_db", "version": ADAPTER_VERSION},
        runtime={"name": "hermes", "source": str(session_row[1] or "")},
        metadata={
            "db_path": str(path),
            "session_id": session_row[0],
            "source": session_row[1],
            "title": session_row[2],
            "started_at": session_row[3],
            "ended_at": session_row[4],
        },
    )
