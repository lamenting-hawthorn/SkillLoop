from __future__ import annotations

from typing import Any

from skillloop.dataset import provenance_for_trace
from skillloop.sanitize import redact_secrets
from skillloop.schema import AgentTrace, Evaluation, Proposal


def export_dpo_records(
    traces: list[AgentTrace],
    evaluations_by_trace: dict[str, Evaluation] | None = None,
    proposals_by_trace: dict[str, list[Proposal]] | None = None,
    include_metadata: bool = True,
) -> list[dict]:
    # V1 conservative behavior: only export explicit preference pairs stored in metadata.
    evaluations_by_trace = evaluations_by_trace or {}
    proposals_by_trace = proposals_by_trace or {}
    records: list[dict] = []
    for trace in traces:
        pair = trace.metadata.get("dpo_pair") if trace.metadata else None
        if pair and {"prompt", "chosen", "rejected"} <= set(pair):
            record: dict[str, Any] = {
                "prompt": redact_secrets(str(pair["prompt"])),
                "chosen": redact_secrets(str(pair["chosen"])),
                "rejected": redact_secrets(str(pair["rejected"])),
            }
            if include_metadata:
                record["metadata"] = provenance_for_trace(
                    trace,
                    evaluation=evaluations_by_trace.get(trace.id),
                    proposals=proposals_by_trace.get(trace.id, []),
                )
            records.append(record)
    return records
