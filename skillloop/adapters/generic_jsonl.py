from __future__ import annotations

import json
from pathlib import Path

from skillloop.sanitize import redact_secrets
from skillloop.schema import AgentMessage, AgentTrace


def load_generic_jsonl(path: str | Path) -> AgentTrace:
    messages: list[AgentMessage] = []
    source_path = Path(path)
    for line_no, line in enumerate(source_path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        data = json.loads(line)
        messages.append(
            AgentMessage(
                role=str(data.get("role", "user")),
                content=redact_secrets(str(data.get("content") or "")),
                metadata={"line_no": line_no, **dict(data.get("metadata") or {})},
            )
        )
    return AgentTrace(source="generic_jsonl", messages=messages, metadata={"path": str(source_path)})
