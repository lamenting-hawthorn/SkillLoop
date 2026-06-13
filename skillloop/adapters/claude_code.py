from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from skillloop.schema import AgentMessage, AgentTrace, ToolCall, sha256_text

ADAPTER_NAME = "claude_code"
ADAPTER_VERSION = "1.0"

_VALID_ROLES = {"system", "user", "assistant", "tool"}


def _message_obj(line: dict[str, Any]) -> dict[str, Any] | None:
    """Return the message dict for a transcript line, or None for meta lines.

    Claude Code session transcripts interleave message lines
    (``{"message": {"role", "content": [...]}, ...}``) with non-message meta
    lines (operation events, summaries) that carry no role/content.
    """
    msg = line.get("message")
    if isinstance(msg, dict) and msg.get("role"):
        return msg
    if line.get("role") and "content" in line:
        return line
    return None


def _text_from_blocks(blocks: list[Any]) -> str:
    parts: list[str] = []
    for block in blocks:
        if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
            parts.append(str(block["text"]))
    return "\n".join(parts)


def _tool_result_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text" and block.get("text") is not None:
                    parts.append(str(block["text"]))
                elif block.get("content") is not None:
                    parts.append(str(block["content"]))
            else:
                parts.append(str(block))
        return "\n".join(parts)
    return str(content)


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def normalize_claude_code_session(raw_text: str, *, include_sidechains: bool = True) -> tuple[list[AgentMessage], dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for raw in raw_text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue  # tolerate a partial trailing line on a live session
        if isinstance(parsed, dict):
            lines.append(parsed)
    if not include_sidechains:
        # Drop subagent sidechain turns before both passes so tool_use/tool_result
        # matching stays internally consistent.
        lines = [line for line in lines if not line.get("isSidechain")]

    # Pass 1: index tool_result blocks by tool_use_id. In the Anthropic message
    # format these arrive in a later user turn, so results are matched back to
    # the assistant's originating tool_use across messages.
    results: dict[str, dict[str, Any]] = {}
    for line in lines:
        msg = _message_obj(line)
        if not msg or not isinstance(msg.get("content"), list):
            continue
        for block in msg["content"]:
            if isinstance(block, dict) and block.get("type") == "tool_result" and block.get("tool_use_id"):
                results[str(block["tool_use_id"])] = {
                    "result": _tool_result_text(block.get("content")),
                    "is_error": bool(block.get("is_error")),
                    "ended_at": line.get("timestamp"),
                }

    # Pass 2: build normalized messages.
    messages: list[AgentMessage] = []
    session_id: Any = None
    for line in lines:
        if session_id is None and line.get("sessionId"):
            session_id = line.get("sessionId")
        msg = _message_obj(line)
        if not msg:
            continue
        role = str(msg.get("role") or "")
        if role not in _VALID_ROLES:
            continue
        content = msg.get("content")
        ts = line.get("timestamp")

        text = ""
        thinking_parts: list[str] = []
        redacted_thinking = False
        tool_calls: list[ToolCall] = []
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = _text_from_blocks(content)
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "thinking":
                    # Forward-compatible: capture extended-thinking text when the
                    # provider includes it. NOTE: Claude Code persists thinking
                    # blocks with an empty text field plus a signature, so the
                    # reasoning text is stripped from the transcript and there is
                    # nothing to preserve from a Claude Code session.
                    if block.get("thinking"):
                        thinking_parts.append(str(block["thinking"]))
                elif btype == "redacted_thinking":
                    redacted_thinking = True
                elif btype == "tool_use":
                    tuid = str(block.get("id") or "")
                    res = results.get(tuid, {})
                    raw_args = block.get("input")
                    arguments = raw_args if isinstance(raw_args, dict) else {}
                    started, ended = _parse_ts(ts), _parse_ts(res.get("ended_at"))
                    duration_ms = int((ended - started).total_seconds() * 1000) if (started and ended) else None
                    status = ("error" if res.get("is_error") else "success") if res else "unknown"
                    tool_calls.append(
                        ToolCall(
                            name=str(block.get("name") or "unknown"),
                            arguments=arguments,
                            result=res.get("result"),
                            id=tuid or None,
                            started_at=ts,
                            ended_at=res.get("ended_at"),
                            duration_ms=duration_ms,
                            status=status,
                        )
                    )

        # Skip turns with no usable signal (e.g. a pure tool_result user turn).
        if not text.strip() and not tool_calls and not thinking_parts:
            continue

        metadata = {
            k: line[k]
            for k in ("uuid", "parentUuid", "isSidechain", "timestamp")
            if line.get(k) is not None
        }
        # Preserve extended-thinking reasoning out of band so it is not lost,
        # while keeping the human-readable content field clean.
        if thinking_parts:
            metadata["thinking"] = "\n".join(thinking_parts)
        if redacted_thinking:
            metadata["thinking_redacted"] = True

        messages.append(
            AgentMessage(role=role, content=text, tool_calls=tool_calls, metadata=metadata)
        )

    meta = {"session_id": session_id, "line_count": len(lines), "message_count": len(messages)}
    return messages, meta


def load_claude_code_session(path: str | Path, *, include_sidechains: bool = True) -> AgentTrace:
    source_path = Path(path).expanduser()
    raw_text = source_path.read_text(encoding="utf-8")
    messages, meta = normalize_claude_code_session(raw_text, include_sidechains=include_sidechains)
    if not messages:
        raise ValueError(f"No usable messages found in Claude Code session: {source_path}")
    return AgentTrace(
        source="claude_code",
        messages=messages,
        adapter={"name": ADAPTER_NAME, "version": ADAPTER_VERSION},
        runtime={"name": "claude_code"},
        metadata={"path": str(source_path), "project": source_path.parent.name, **meta},
        raw_artifact_ref=str(source_path),
        raw_trace_sha256=sha256_text(raw_text),
    )


def latest_claude_code_session(projects_dir: str | Path | None = None, project: str | None = None) -> Path:
    """Newest Claude Code session transcript, without mutating anything.

    Session files live one level under each project: ``<projects_dir>/<slug>/<id>.jsonl``.
    Subagent transcripts under ``<slug>/subagents/`` are intentionally excluded.
    """
    base = Path(projects_dir).expanduser() if projects_dir else (Path.home() / ".claude" / "projects")
    if not base.exists():
        raise FileNotFoundError(f"Claude Code projects dir not found: {base}")
    candidates = list((base / project).glob("*.jsonl")) if project else list(base.glob("*/*.jsonl"))
    if not candidates:
        raise FileNotFoundError(f"No Claude Code session transcripts found under {base}")
    return max(candidates, key=lambda p: p.stat().st_mtime)
