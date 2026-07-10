from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from skillloop.eval.registry import EvaluatorRegistry
from skillloop.schema import AgentTrace, Evaluation, now_iso, sha256_text, stable_json_dumps


@dataclass
class ReplayCaseResult:
    trace_id: str
    scores: dict[str, int]
    deltas: dict[str, int]
    tags: dict[str, list[str]]
    evidence_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "scores": self.scores,
            "deltas": self.deltas,
            "tags": self.tags,
            "evidence_counts": self.evidence_counts,
        }


@dataclass
class BenchmarkReport:
    baseline: str
    candidates: list[str]
    created_at: str
    cases: list[ReplayCaseResult]
    summary: dict[str, Any]
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = sha256_text(
                stable_json_dumps(
                    {
                        "baseline": self.baseline,
                        "candidates": self.candidates,
                        "created_at": self.created_at,
                    }
                )
            )[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "baseline": self.baseline,
            "candidates": self.candidates,
            "summary": self.summary,
            "cases": [case.to_dict() for case in self.cases],
        }


def _run_evaluator(registry: EvaluatorRegistry, trace: AgentTrace, name: str) -> Evaluation:
    return registry.evaluate(trace, name=name)


def replay_benchmark(
    traces: list[AgentTrace],
    registry: EvaluatorRegistry,
    baseline: str = "rubric_legacy",
    candidates: list[str] | None = None,
) -> BenchmarkReport:
    candidates = candidates or ["rubric"]
    cases: list[ReplayCaseResult] = []
    improved_counts = dict.fromkeys(candidates, 0)
    regressed_counts = dict.fromkeys(candidates, 0)
    unchanged_counts = dict.fromkeys(candidates, 0)
    evidence_improved_counts = dict.fromkeys(candidates, 0)
    stricter_failure_detection_counts = dict.fromkeys(candidates, 0)
    total_delta = dict.fromkeys(candidates, 0)

    for trace in traces:
        baseline_eval = _run_evaluator(registry, trace, baseline)
        scores = {baseline: baseline_eval.score}
        tags = {baseline: baseline_eval.tags}
        evidence_counts = {baseline: len(baseline_eval.evidence)}
        deltas: dict[str, int] = {}
        for candidate in candidates:
            candidate_eval = _run_evaluator(registry, trace, candidate)
            scores[candidate] = candidate_eval.score
            tags[candidate] = candidate_eval.tags
            evidence_counts[candidate] = len(candidate_eval.evidence)
            delta = candidate_eval.score - baseline_eval.score
            deltas[candidate] = delta
            total_delta[candidate] += delta
            if len(candidate_eval.evidence) > len(baseline_eval.evidence):
                evidence_improved_counts[candidate] += 1
            if "tool_failure" in candidate_eval.tags and "tool_failure" not in baseline_eval.tags:
                stricter_failure_detection_counts[candidate] += 1
            if delta > 0:
                improved_counts[candidate] += 1
            elif delta < 0:
                regressed_counts[candidate] += 1
            else:
                unchanged_counts[candidate] += 1
        cases.append(
            ReplayCaseResult(
                trace_id=trace.id,
                scores=scores,
                deltas=deltas,
                tags=tags,
                evidence_counts=evidence_counts,
            )
        )

    summary = {
        "traces": len(traces),
        "baseline": baseline,
        "candidates": candidates,
        "improved_counts": improved_counts,
        "regressed_counts": regressed_counts,
        "unchanged_counts": unchanged_counts,
        "evidence_improved_counts": evidence_improved_counts,
        "stricter_failure_detection_counts": stricter_failure_detection_counts,
        "average_delta": {
            candidate: round(total_delta[candidate] / len(traces), 2) if traces else 0
            for candidate in candidates
        },
        "quality_improved_counts": {
            candidate: improved_counts[candidate]
            + evidence_improved_counts[candidate]
            + stricter_failure_detection_counts[candidate]
            for candidate in candidates
        },
        "training_ready_signal": all(
            improved_counts[candidate]
            + evidence_improved_counts[candidate]
            + stricter_failure_detection_counts[candidate]
            > 0
            for candidate in candidates
        )
        if traces
        else False,
    }
    return BenchmarkReport(
        baseline=baseline, candidates=candidates, created_at=now_iso(), cases=cases, summary=summary
    )


def write_benchmark_report(path: str | Path, report: BenchmarkReport) -> Path:
    out = Path(path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return out
