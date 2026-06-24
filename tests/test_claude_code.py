from __future__ import annotations

import json
import os

import pytest

from skillloop.adapters.claude_code import latest_claude_code_session, load_claude_code_session


def _write_session(path, lines):
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")


def test_claude_code_adapter_parses_blocks_and_tool_results(tmp_path):
    lines = [
        {"type": "summary", "summary": "meta line, no message"},
        {"type": "user", "uuid": "u1", "timestamp": "2026-06-13T10:00:00Z",
         "message": {"role": "user", "content": [{"type": "text", "text": "fix the bug"}]}},
        {"type": "assistant", "uuid": "a1", "timestamp": "2026-06-13T10:00:01Z",
         "message": {"role": "assistant", "content": [
             {"type": "text", "text": "running tests"},
             {"type": "tool_use", "id": "toolu_1", "name": "Bash", "input": {"command": "pytest"}},
         ]}},
        {"type": "user", "uuid": "u2", "timestamp": "2026-06-13T10:00:03Z",
         "message": {"role": "user", "content": [
             {"type": "tool_result", "tool_use_id": "toolu_1", "content": "2 passed", "is_error": False},
         ]}},
        {"type": "assistant", "uuid": "a2", "timestamp": "2026-06-13T10:00:04Z",
         "message": {"role": "assistant", "content": [{"type": "text", "text": "done, tests pass"}]}},
    ]
    session = tmp_path / "session.jsonl"
    _write_session(session, lines)

    trace = load_claude_code_session(session)

    assert trace.source == "claude_code"
    assert trace.adapter["name"] == "claude_code"
    # the meta line and the pure tool_result turn carry no signal and are dropped
    assert [m.role for m in trace.messages] == ["user", "assistant", "assistant"]
    assert trace.messages[0].content == "fix the bug"

    asst = trace.messages[1]
    assert asst.content == "running tests"
    assert len(asst.tool_calls) == 1
    call = asst.tool_calls[0]
    assert call.name == "Bash"
    assert call.arguments == {"command": "pytest"}
    assert call.result == "2 passed"
    assert call.status == "success"
    assert call.success is True
    assert call.duration_ms == 2000  # 10:00:01 -> 10:00:03

    assert trace.messages[2].content == "done, tests pass"


def test_claude_code_adapter_rejects_empty_session(tmp_path):
    session = tmp_path / "empty.jsonl"
    _write_session(session, [{"type": "summary", "summary": "only meta"}])
    try:
        load_claude_code_session(session)
    except ValueError:
        return
    raise AssertionError("expected ValueError for a session with no usable messages")


def test_claude_code_adapter_rejects_malformed_non_trailing_line(tmp_path):
    session = tmp_path / "malformed_mid.jsonl"
    session.write_text(
        "\n".join(
            [
                json.dumps({"message": {"role": "user", "content": [{"type": "text", "text": "hi"}]}}),
                '{"message": ',
                json.dumps({"message": {"role": "assistant", "content": [{"type": "text", "text": "bye"}]}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_claude_code_session(session)


def test_claude_code_adapter_tolerates_malformed_trailing_line(tmp_path):
    session = tmp_path / "live_partial.jsonl"
    session.write_text(
        json.dumps({"message": {"role": "user", "content": [{"type": "text", "text": "hi"}]}})
        + "\n"
        + '{"message": '
        + "\n",
        encoding="utf-8",
    )

    trace = load_claude_code_session(session)

    assert [message.content for message in trace.messages] == ["hi"]


def test_latest_claude_code_session_picks_newest(tmp_path):
    proj = tmp_path / "proj-a"
    proj.mkdir()
    older, newer = proj / "older.jsonl", proj / "newer.jsonl"
    msg = {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "hi"}]}}
    _write_session(older, [msg])
    _write_session(newer, [msg])
    os.utime(older, (1, 1))
    os.utime(newer, (10, 10))
    assert latest_claude_code_session(tmp_path).name == "newer.jsonl"


def test_claude_code_preserves_thinking_in_metadata(tmp_path):
    lines = [
        {"type": "assistant", "uuid": "a1", "timestamp": "2026-06-13T10:00:00Z",
         "message": {"role": "assistant", "content": [
             {"type": "thinking", "thinking": "the user wants X, so I should do Y"},
             {"type": "text", "text": "here is the answer"},
         ]}},
    ]
    session = tmp_path / "thinking.jsonl"
    _write_session(session, lines)
    trace = load_claude_code_session(session)

    assert len(trace.messages) == 1
    msg = trace.messages[0]
    assert msg.content == "here is the answer"  # content is not muddied by thinking
    assert msg.metadata.get("thinking") == "the user wants X, so I should do Y"


def test_claude_code_no_sidechains_filter(tmp_path):
    lines = [
        {"type": "user", "uuid": "u1",
         "message": {"role": "user", "content": [{"type": "text", "text": "main turn"}]}},
        {"type": "assistant", "uuid": "s1", "isSidechain": True,
         "message": {"role": "assistant", "content": [{"type": "text", "text": "subagent turn"}]}},
    ]
    session = tmp_path / "sidechain.jsonl"
    _write_session(session, lines)

    full = load_claude_code_session(session, include_sidechains=True)
    assert [m.content for m in full.messages] == ["main turn", "subagent turn"]

    filtered = load_claude_code_session(session, include_sidechains=False)
    assert [m.content for m in filtered.messages] == ["main turn"]


def test_claude_code_empty_thinking_text_is_not_preserved(tmp_path):
    # Claude Code persists thinking blocks with empty text and only a signature,
    # so there is no reasoning text to capture.
    lines = [
        {"type": "assistant", "uuid": "a1",
         "message": {"role": "assistant", "content": [
             {"type": "thinking", "thinking": "", "signature": "sig-abc"},
             {"type": "text", "text": "answer"},
         ]}},
    ]
    session = tmp_path / "empty_think.jsonl"
    _write_session(session, lines)
    msg = load_claude_code_session(session).messages[0]
    assert msg.content == "answer"
    assert "thinking" not in msg.metadata
