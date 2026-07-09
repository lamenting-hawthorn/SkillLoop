from __future__ import annotations

import argparse
from pathlib import Path

from skillloop.conditions import LoopCondition
from skillloop.policy import SkillLoopPolicy
from skillloop.schema import AgentTrace, Proposal
from skillloop.store import SkillLoopStore


def _store(args: argparse.Namespace) -> SkillLoopStore:
    return SkillLoopStore(Path(args.path))


def _policy_path(store: SkillLoopStore) -> Path:
    return store.state_dir / "policy.json"


def _load_policy(store: SkillLoopStore) -> SkillLoopPolicy:
    return SkillLoopPolicy.load(_policy_path(store)) if _policy_path(store).exists() else SkillLoopPolicy.default()


def _format_count(label: str, count: int) -> str:
    return f"{label}: {count}"


def _resolve_trace(store: SkillLoopStore, trace_ref: str) -> AgentTrace:
    traces = store.list_traces()
    if trace_ref == "latest":
        if not traces:
            raise SystemExit("No traces found. Run `skillloop ingest ...` first.")
        return traces[0]
    matches = [trace for trace in traces if trace.id == trace_ref or trace.id.startswith(trace_ref)]
    if not matches:
        raise SystemExit(f"Trace not found: {trace_ref}")
    if len(matches) > 1:
        raise SystemExit(f"Trace id prefix is ambiguous: {trace_ref}")
    return matches[0]


def _resolve_proposal(store: SkillLoopStore, proposal_ref: str) -> Proposal:
    proposals = store.list_proposals(status=None)
    matches = [proposal for proposal in proposals if proposal.id == proposal_ref or proposal.id.startswith(proposal_ref)]
    if not matches:
        raise SystemExit(f"Proposal not found: {proposal_ref}")
    if len(matches) > 1:
        raise SystemExit(f"Proposal id prefix is ambiguous: {proposal_ref}")
    return matches[0]


def _condition_from_args(args: argparse.Namespace) -> LoopCondition:
    if getattr(args, "condition", None):
        condition = LoopCondition.from_json(args.condition)
        if not getattr(args, "min_score_explicit", False):
            return condition
        return LoopCondition(
            score_gte=args.min_score,
            required_tags=condition.required_tags,
            forbidden_tags=condition.forbidden_tags,
            max_iterations=condition.max_iterations,
        )
    return LoopCondition(
        score_gte=args.min_score,
        required_tags=tuple(getattr(args, "require_tag", []) or []),
        forbidden_tags=tuple(getattr(args, "forbid_tag", []) or []),
        max_iterations=getattr(args, "max_iterations", None),
    )


def _service_interval_seconds(args: argparse.Namespace) -> int:
    interval = int(args.interval_seconds)
    if interval <= 0:
        raise SystemExit("--interval-seconds must be positive")
    return interval


__all__ = [
    "_store",
    "_policy_path",
    "_load_policy",
    "_format_count",
    "_resolve_trace",
    "_resolve_proposal",
    "_condition_from_args",
    "_service_interval_seconds",
]
