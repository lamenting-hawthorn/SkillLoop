from __future__ import annotations

from skillloop.sanitize import redact_secrets
from skillloop.schema import AgentTrace


def export_sft_records(traces: list[AgentTrace]) -> list[dict]:
    records: list[dict] = []
    for trace in traces:
        messages = [
            {"role": message.role, "content": redact_secrets(message.content)}
            for message in trace.messages
            if message.role in {"system", "user", "assistant"} and message.content.strip()
        ]
        if any(m["role"] == "user" for m in messages) and any(m["role"] == "assistant" for m in messages):
            records.append({"messages": messages})
    return records
