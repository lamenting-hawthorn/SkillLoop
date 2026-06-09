from __future__ import annotations

from skillloop.schema import AgentMessage, ToolCall


def _command_text(call: ToolCall) -> str:
    command = call.arguments.get("command") or call.arguments.get("cmd") or call.arguments.get("input") or ""
    return str(command).lower()


def command_execution_evidence(calls: list[ToolCall]) -> list[dict[str, object]]:
    evidence: list[dict[str, object]] = []
    for call in calls:
        if call.name not in {"terminal", "execute_code", "shell", "bash"}:
            continue
        evidence.append(
            {
                "kind": "command_execution",
                "tool_call_id": call.id,
                "tool_name": call.name,
                "status": call.status,
                "exit_code": call.exit_code,
                "duration_ms": call.duration_ms,
                "command": _command_text(call)[:240],
            }
        )
    return evidence


def test_execution_evidence(calls: list[ToolCall]) -> list[dict[str, object]]:
    evidence: list[dict[str, object]] = []
    for call in calls:
        command = _command_text(call)
        result = str(call.result or "").lower()
        if not any(marker in f"{command}\n{result}" for marker in ("pytest", "unittest", "tests/", "passed", "failed")):
            continue
        evidence.append(
            {
                "kind": "test_execution",
                "tool_call_id": call.id,
                "status": call.status,
                "exit_code": call.exit_code,
                "passed": call.status == "success" or "passed" in result,
                "failed": call.status == "error" or "failed" in result,
            }
        )
    return evidence


def file_artifact_evidence(calls: list[ToolCall]) -> list[dict[str, object]]:
    return [
        {
            "kind": "file_artifact",
            "tool_call_id": call.id,
            "artifact_refs": call.artifact_refs,
        }
        for call in calls
        if call.artifact_refs
    ]


def user_feedback_evidence(messages: list[AgentMessage], correction_words: tuple[str, ...], learning_words: tuple[str, ...]) -> list[dict[str, object]]:
    evidence: list[dict[str, object]] = []
    for index, message in enumerate(messages):
        if message.role != "user":
            continue
        lowered = message.content.lower()
        if any(word in lowered for word in correction_words):
            evidence.append({"kind": "user_feedback", "subtype": "correction", "message_index": index})
        if any(word in lowered for word in learning_words):
            evidence.append({"kind": "user_feedback", "subtype": "learning_signal", "message_index": index})
    return evidence
