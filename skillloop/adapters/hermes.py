from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from skillloop.schema import AgentMessage, AgentTrace, ToolCall


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
                )
            )
        messages.append(
            AgentMessage(
                role=role,
                content=str(item.get("content") or item.get("text") or ""),
                tool_calls=tool_calls,
                metadata={k: v for k, v in item.items() if k not in {"role", "content", "text", "tool_calls"}},
            )
        )
    return AgentTrace(
        source="hermes",
        messages=messages,
        metadata={"session_id": data.get("session_id") or data.get("id"), "raw_keys": sorted(data.keys())},
    )


def load_hermes_export(path: str | Path) -> AgentTrace:
    return normalize_hermes_export(json.loads(Path(path).read_text()))
