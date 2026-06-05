from __future__ import annotations

from skillloop.schema import AgentTrace


def export_dpo_records(traces: list[AgentTrace]) -> list[dict]:
    # V1 conservative behavior: only export explicit preference pairs stored in metadata.
    records: list[dict] = []
    for trace in traces:
        pair = trace.metadata.get("dpo_pair") if trace.metadata else None
        if pair and {"prompt", "chosen", "rejected"} <= set(pair):
            records.append({"prompt": pair["prompt"], "chosen": pair["chosen"], "rejected": pair["rejected"]})
    return records
