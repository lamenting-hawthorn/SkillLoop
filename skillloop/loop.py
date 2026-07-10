from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from skillloop.conditions import LoopCondition
from skillloop.distill.memory import DISTILLER_NAME as MEMORY_DISTILLER_NAME
from skillloop.distill.memory import DISTILLER_VERSION as MEMORY_DISTILLER_VERSION
from skillloop.distill.memory import propose_memory_updates
from skillloop.distill.skills import DISTILLER_NAME as SKILL_DISTILLER_NAME
from skillloop.distill.skills import DISTILLER_VERSION as SKILL_DISTILLER_VERSION
from skillloop.distill.skills import propose_skill_updates
from skillloop.eval.registry import EvaluatorRegistry, default_evaluator_registry
from skillloop.provenance import annotate_proposal_provenance
from skillloop.schema import Evaluation, Proposal, now_iso
from skillloop.store import SkillLoopStore

SCHEDULE_VERSION = "1.0"
_INTERVALS = {
    "hourly": timedelta(hours=1),
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
}


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class LoopRunSummary:
    traces_seen: int = 0
    traces_evaluated: int = 0
    traces_skipped: int = 0
    failing_traces: list[str] = field(default_factory=list)
    done_traces: list[str] = field(default_factory=list)
    stopped_traces: list[str] = field(default_factory=list)
    proposals_created: int = 0
    duplicate_proposals: int = 0
    evaluations: list[Evaluation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "traces_seen": self.traces_seen,
            "traces_evaluated": self.traces_evaluated,
            "traces_skipped": self.traces_skipped,
            "failing_traces": self.failing_traces,
            "done_traces": self.done_traces,
            "stopped_traces": self.stopped_traces,
            "proposals_created": self.proposals_created,
            "duplicate_proposals": self.duplicate_proposals,
            "evaluations": [evaluation.to_dict() for evaluation in self.evaluations],
        }


@dataclass
class LoopSchedule:
    interval: str = "daily"
    evaluator: str = "rubric"
    min_score: int = 70
    condition: LoopCondition = field(default_factory=LoopCondition)
    only_unevaluated: bool = True
    distill_failures: bool = True
    limit: int | None = None
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    last_run_at: str | None = None
    next_run_at: str | None = None
    version: str = SCHEDULE_VERSION

    def __post_init__(self) -> None:
        if self.interval not in _INTERVALS:
            raise ValueError(f"unsupported loop interval: {self.interval}")
        self.min_score = int(self.min_score)
        if not isinstance(self.condition, LoopCondition):
            self.condition = LoopCondition.from_dict(dict(self.condition or {}))
        if self.condition.score_gte != self.min_score:
            self.condition = LoopCondition(
                score_gte=self.min_score,
                required_tags=self.condition.required_tags,
                forbidden_tags=self.condition.forbidden_tags,
                max_iterations=self.condition.max_iterations,
            )
        self.only_unevaluated = bool(self.only_unevaluated)
        self.distill_failures = bool(self.distill_failures)
        self.limit = int(self.limit) if self.limit is not None else None
        self.next_run_at = self.next_run_at or self.compute_next_run(utc_now()).isoformat()

    def compute_next_run(self, base: datetime) -> datetime:
        return (base.astimezone(UTC) + _INTERVALS[self.interval]).replace(microsecond=0)

    def due(self, at: datetime | None = None) -> bool:
        at = at or utc_now()
        next_run = parse_iso(self.next_run_at)
        return next_run is None or at.astimezone(UTC) >= next_run

    def mark_run(self, at: datetime | None = None) -> None:
        at = (at or utc_now()).astimezone(UTC).replace(microsecond=0)
        self.last_run_at = at.isoformat()
        self.next_run_at = self.compute_next_run(at).isoformat()
        self.updated_at = now_iso()

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "interval": self.interval,
            "evaluator": self.evaluator,
            "min_score": self.min_score,
            "condition": self.condition.to_dict(),
            "only_unevaluated": self.only_unevaluated,
            "distill_failures": self.distill_failures,
            "limit": self.limit,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_run_at": self.last_run_at,
            "next_run_at": self.next_run_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LoopSchedule:
        return cls(
            version=str(data.get("version") or SCHEDULE_VERSION),
            interval=str(data.get("interval") or "daily"),
            evaluator=str(data.get("evaluator") or "rubric"),
            min_score=int(data.get("min_score") or 70),
            condition=LoopCondition.from_dict(
                data.get("condition") or {"score_gte": int(data.get("min_score") or 70)}
            ),
            only_unevaluated=bool(data.get("only_unevaluated", True)),
            distill_failures=bool(data.get("distill_failures", True)),
            limit=data.get("limit"),
            created_at=str(data.get("created_at") or now_iso()),
            updated_at=str(data.get("updated_at") or now_iso()),
            last_run_at=data.get("last_run_at"),
            next_run_at=data.get("next_run_at"),
        )


def schedule_path(store: SkillLoopStore) -> Path:
    return store.state_dir / "loop_schedule.json"


def save_schedule(store: SkillLoopStore, schedule: LoopSchedule) -> Path:
    store.init()
    path = schedule_path(store)
    path.write_text(
        json.dumps(schedule.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return path


def load_schedule(store: SkillLoopStore) -> LoopSchedule:
    path = schedule_path(store)
    if not path.exists():
        raise FileNotFoundError(f"loop schedule not found: {path}")
    return LoopSchedule.from_dict(json.loads(path.read_text(encoding="utf-8")))


def proposals_with_provenance(
    trace_id: str, proposals: list[Proposal], source_evaluation: Evaluation | None
) -> list[Proposal]:
    annotated: list[Proposal] = []
    for proposal in proposals:
        if proposal.kind == "memory":
            annotate_proposal_provenance(
                proposal,
                source_evaluation=source_evaluation,
                producer_name=MEMORY_DISTILLER_NAME,
                producer_version=MEMORY_DISTILLER_VERSION,
                producer_func=propose_memory_updates,
            )
        elif proposal.kind == "skill":
            annotate_proposal_provenance(
                proposal,
                source_evaluation=source_evaluation,
                producer_name=SKILL_DISTILLER_NAME,
                producer_version=SKILL_DISTILLER_VERSION,
                producer_func=propose_skill_updates,
            )
        proposal.trace_id = trace_id
        annotated.append(proposal)
    return annotated


def run_outer_loop(
    store: SkillLoopStore,
    *,
    evaluator: str = "rubric",
    min_score: int = 70,
    condition: LoopCondition | None = None,
    only_unevaluated: bool = True,
    distill_failures: bool = True,
    limit: int | None = None,
    registry: EvaluatorRegistry | None = None,
) -> LoopRunSummary:
    registry = registry or default_evaluator_registry()
    condition = condition or LoopCondition(score_gte=min_score)
    traces = store.list_traces()
    if limit is not None:
        traces = traces[: int(limit)]
    summary = LoopRunSummary(traces_seen=len(traces))

    for trace in traces:
        prior_iterations = len(store.list_evaluations(trace.id))
        if only_unevaluated and prior_iterations > 0:
            summary.traces_skipped += 1
            continue
        evaluation = registry.evaluate(trace, name=evaluator)
        condition_result = condition.annotate(evaluation, prior_iterations=prior_iterations)
        store.save_evaluation(evaluation)
        summary.traces_evaluated += 1
        summary.evaluations.append(evaluation)
        if condition_result.passed:
            summary.done_traces.append(trace.id)
            continue
        summary.failing_traces.append(trace.id)
        if not condition_result.should_continue:
            summary.stopped_traces.append(trace.id)
            continue
        if distill_failures:
            proposals = proposals_with_provenance(
                trace.id, propose_memory_updates(trace) + propose_skill_updates(trace), evaluation
            )
            for proposal in proposals:
                saved_id = store.save_proposal(proposal)
                if saved_id == proposal.id:
                    summary.proposals_created += 1
                else:
                    summary.duplicate_proposals += 1

    return summary


def tick(
    store: SkillLoopStore, *, force: bool = False
) -> tuple[bool, LoopRunSummary | None, LoopSchedule]:
    schedule = load_schedule(store)
    if not force and not schedule.due():
        return False, None, schedule
    summary = run_outer_loop(
        store,
        evaluator=schedule.evaluator,
        min_score=schedule.min_score,
        condition=schedule.condition,
        only_unevaluated=schedule.only_unevaluated,
        distill_failures=schedule.distill_failures,
        limit=schedule.limit,
    )
    schedule.mark_run()
    save_schedule(store, schedule)
    return True, summary, schedule
