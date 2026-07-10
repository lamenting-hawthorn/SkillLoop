from __future__ import annotations

from typing import Any

from skillloop.dataset import provenance_for_trace
from skillloop.sanitize import redact_secrets
from skillloop.schema import AgentTrace, Evaluation, Proposal


def export_sft_records(
    traces: list[AgentTrace],
    evaluations_by_trace: dict[str, Evaluation] | None = None,
    proposals_by_trace: dict[str, list[Proposal]] | None = None,
    include_metadata: bool = True,
) -> list[dict]:
    evaluations_by_trace = evaluations_by_trace or {}
    proposals_by_trace = proposals_by_trace or {}
    records: list[dict] = []
    for trace in traces:
        messages = [
            {"role": message.role, "content": redact_secrets(message.content)}
            for message in trace.messages
            if message.role in {"system", "user", "assistant"} and message.content.strip()
        ]
        if any(m["role"] == "user" for m in messages) and any(
            m["role"] == "assistant" for m in messages
        ):
            record: dict[str, Any] = {"messages": messages}
            if include_metadata:
                record["metadata"] = provenance_for_trace(
                    trace,
                    evaluation=evaluations_by_trace.get(trace.id),
                    proposals=proposals_by_trace.get(trace.id, []),
                )
            records.append(record)
    return records
