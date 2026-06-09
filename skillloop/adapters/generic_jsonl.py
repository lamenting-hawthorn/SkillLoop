from __future__ import annotations

import json
from pathlib import Path

from skillloop.sanitize import redact_secrets
from skillloop.schema import AgentMessage, AgentTrace, sha256_text

ADAPTER_NAME = "generic_jsonl"
ADAPTER_VERSION = "1.1"


def load_generic_jsonl(path: str | Path) -> AgentTrace:
    messages: list[AgentMessage] = []
    source_path = Path(path)
    raw_text = source_path.read_text()
    for line_no, line in enumerate(raw_text.splitlines(), start=1):
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
    return AgentTrace(
        source="generic_jsonl",
        messages=messages,
        adapter={"name": ADAPTER_NAME, "version": ADAPTER_VERSION},
        metadata={"path": str(source_path)},
        raw_artifact_ref=str(source_path),
        raw_trace_sha256=sha256_text(raw_text),
    )
