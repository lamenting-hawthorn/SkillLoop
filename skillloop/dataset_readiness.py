from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from skillloop.dataset import estimate_tokens, record_text
from skillloop.schema import AgentTrace, Evaluation


@dataclass(frozen=True)
class DatasetReadinessPolicy:
    min_records: int = 10
    min_estimated_tokens: int = 500
    require_non_empty_splits: bool = True
    require_metadata: bool = True
    require_hashes: bool = True


@dataclass
class DatasetReadinessReport:
    ready: bool
    checks: dict[str, bool]
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "checks": self.checks,
            "warnings": self.warnings,
            "stats": self.stats,
        }


def _all_records(split_records_map: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [record for records in split_records_map.values() for record in records]


def _metadata_complete(records: list[dict[str, Any]]) -> bool:
    required = {"trace_id", "normalized_trace_sha256", "evaluation_id", "evaluation_score"}
    return all(required <= set(record.get("metadata") or {}) for record in records)


def _hashes_complete(traces: list[AgentTrace], evaluations_by_trace: dict[str, Evaluation]) -> bool:
    if not traces:
        return False
    for trace in traces:
        if not (trace.normalized_trace_sha256 or trace.compute_normalized_sha256()):
            return False
        evaluation = evaluations_by_trace.get(trace.id)
        if evaluation is None or not (
            evaluation.artifact_sha256 or evaluation.compute_artifact_sha256()
        ):
            return False
    return True


def _sensitive_artifact_ref_warnings(records: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    for record in records:
        metadata = record.get("metadata") or {}
        for key, value in metadata.items():
            if key.endswith("artifact_ref") and isinstance(value, str) and value.startswith("/"):
                warnings.append(f"absolute artifact reference in metadata: {key}")
    return warnings


def assess_dataset_readiness(
    *,
    split_records_map: dict[str, list[dict[str, Any]]],
    source_traces: list[AgentTrace],
    evaluations_by_trace: dict[str, Evaluation],
    policy: DatasetReadinessPolicy | None = None,
) -> DatasetReadinessReport:
    policy = policy or DatasetReadinessPolicy()
    records = _all_records(split_records_map)
    estimated_tokens = sum(estimate_tokens(record_text(record)) for record in records)
    empty_splits = [name for name, split_records in split_records_map.items() if not split_records]
    checks = {
        "min_records": len(records) >= policy.min_records,
        "min_estimated_tokens": estimated_tokens >= policy.min_estimated_tokens,
        "non_empty_splits": not policy.require_non_empty_splits or not empty_splits,
        "metadata": not policy.require_metadata or _metadata_complete(records),
        "hashes": not policy.require_hashes
        or _hashes_complete(source_traces, evaluations_by_trace),
    }
    warnings: list[str] = []
    if empty_splits:
        warnings.append(f"empty dataset splits: {', '.join(empty_splits)}")
    warnings.extend(_sensitive_artifact_ref_warnings(records))
    return DatasetReadinessReport(
        ready=all(checks.values()),
        checks=checks,
        warnings=warnings,
        stats={
            "records": len(records),
            "estimated_tokens": estimated_tokens,
            "split_records": {
                name: len(split_records) for name, split_records in split_records_map.items()
            },
            "min_records": policy.min_records,
            "min_estimated_tokens": policy.min_estimated_tokens,
        },
    )
