from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from skillloop.schema import (
    AgentTrace,
    Evaluation,
    Proposal,
    now_iso,
    sha256_text,
    stable_json_dumps,
)


def estimate_tokens(text: str) -> int:
    """Deterministic stdlib token estimate for planning/export stats.

    This is not tokenizer-specific; it intentionally provides a cheap, stable
    approximation until training integrations choose a concrete tokenizer.
    """
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def record_text(record: dict[str, Any]) -> str:
    if "messages" in record:
        return "\n".join(str(message.get("content", "")) for message in record.get("messages", []))
    return "\n".join(str(record.get(key, "")) for key in ("prompt", "chosen", "rejected"))


def record_stats(records: list[dict[str, Any]]) -> dict[str, Any]:
    token_counts = [estimate_tokens(record_text(record)) for record in records]
    return {
        "records": len(records),
        "estimated_tokens": sum(token_counts),
        "min_estimated_tokens": min(token_counts, default=0),
        "max_estimated_tokens": max(token_counts, default=0),
        "avg_estimated_tokens": round(sum(token_counts) / len(token_counts), 2)
        if token_counts
        else 0,
    }


def split_records(
    records: list[dict[str, Any]], ratios: dict[str, float] | None = None
) -> dict[str, list[dict[str, Any]]]:
    ratios = ratios or {"train": 1.0}
    if not records:
        return {name: [] for name in ratios}
    names = list(ratios)
    total_ratio = sum(max(0.0, value) for value in ratios.values()) or 1.0
    normalized = {name: max(0.0, ratios[name]) / total_ratio for name in names}
    ordered = sorted(records, key=lambda record: stable_json_dumps(record.get("metadata", record)))
    result = {name: [] for name in names}
    cumulative: list[tuple[str, float]] = []
    running = 0.0
    for name in names:
        running += normalized[name]
        cumulative.append((name, running))
    for index, record in enumerate(ordered):
        point = (index + 0.5) / len(ordered)
        for name, threshold in cumulative:
            if point <= threshold:
                result[name].append(record)
                break
        else:
            result[names[-1]].append(record)
    return result


def parse_split_spec(spec: str | None) -> dict[str, float]:
    if not spec:
        return {"train": 1.0}
    ratios: dict[str, float] = {}
    for chunk in spec.split(","):
        if not chunk.strip():
            continue
        if "=" not in chunk:
            raise ValueError(f"invalid split chunk: {chunk!r}; expected name=ratio")
        name, raw_value = chunk.split("=", 1)
        name = name.strip()
        if not name:
            raise ValueError("split name cannot be empty")
        value = float(raw_value)
        if value < 0:
            raise ValueError(f"split ratio cannot be negative: {name}")
        ratios[name] = value
    if not ratios:
        raise ValueError("split spec produced no splits")
    return ratios


def provenance_for_trace(
    trace: AgentTrace, evaluation: Evaluation | None = None, proposals: list[Proposal] | None = None
) -> dict[str, Any]:
    proposals = proposals or []
    return {
        "trace_id": trace.id,
        "trace_schema_version": trace.schema_version,
        "trace_source": trace.source,
        "raw_trace_sha256": trace.raw_trace_sha256,
        "normalized_trace_sha256": trace.normalized_trace_sha256
        or trace.compute_normalized_sha256(),
        "evaluation_id": evaluation.id if evaluation else None,
        "evaluation_score": evaluation.score if evaluation else None,
        "evaluator_name": evaluation.evaluator_name if evaluation else None,
        "evaluator_version": evaluation.evaluator_version if evaluation else None,
        "proposal_ids": [proposal.id for proposal in proposals],
        "proposal_hashes": [proposal.content_hash for proposal in proposals],
    }


def write_jsonl(path: str | Path, records: list[dict[str, Any]]) -> Path:
    out = Path(path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records)
        + ("\n" if records else ""),
        encoding="utf-8",
    )
    return out


@dataclass
class DatasetManifest:
    kind: str
    created_at: str
    records: int
    estimated_tokens: int
    output_files: dict[str, str]
    splits: dict[str, dict[str, Any]]
    export_metadata: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = sha256_text(
                stable_json_dumps(
                    {
                        "kind": self.kind,
                        "created_at": self.created_at,
                        "output_files": self.output_files,
                    }
                )
            )[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "created_at": self.created_at,
            "records": self.records,
            "estimated_tokens": self.estimated_tokens,
            "output_files": self.output_files,
            "splits": self.splits,
            "export_metadata": self.export_metadata,
            "provenance": self.provenance,
        }


def build_manifest(
    *,
    kind: str,
    split_outputs: dict[str, Path],
    split_records_map: dict[str, list[dict[str, Any]]],
    source_traces: list[AgentTrace],
    evaluations_by_trace: dict[str, Evaluation] | None = None,
    proposals_by_trace: dict[str, list[Proposal]] | None = None,
    export_metadata: dict[str, Any] | None = None,
) -> DatasetManifest:
    evaluations_by_trace = evaluations_by_trace or {}
    proposals_by_trace = proposals_by_trace or {}
    all_records = [record for records in split_records_map.values() for record in records]
    stats = record_stats(all_records)
    evaluator_counts = Counter(
        evaluation.evaluator_name for evaluation in evaluations_by_trace.values()
    )
    manifest = DatasetManifest(
        kind=kind,
        created_at=now_iso(),
        records=stats["records"],
        estimated_tokens=stats["estimated_tokens"],
        output_files={name: str(path) for name, path in split_outputs.items()},
        splits={name: record_stats(records) for name, records in split_records_map.items()},
        export_metadata={
            "format": kind,
            "schema_version": "1.0",
            **(export_metadata or {}),
        },
        provenance={
            "trace_ids": [trace.id for trace in source_traces],
            "trace_schema_versions": sorted({trace.schema_version for trace in source_traces}),
            "evaluation_ids": [evaluation.id for evaluation in evaluations_by_trace.values()],
            "evaluator_counts": dict(evaluator_counts),
            "proposal_ids": [
                proposal.id for proposals in proposals_by_trace.values() for proposal in proposals
            ],
        },
    )
    return manifest  # noqa: RET504


def write_manifest(path: str | Path, manifest: DatasetManifest) -> Path:
    out = Path(path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return out
