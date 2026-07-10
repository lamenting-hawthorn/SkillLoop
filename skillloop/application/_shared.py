from __future__ import annotations

from pathlib import Path

from skillloop.policy import SkillLoopPolicy
from skillloop.schema import AgentTrace, Evaluation, Proposal
from skillloop.store import SkillLoopStore


def load_policy(store: SkillLoopStore) -> SkillLoopPolicy:
    path = store.state_dir / "policy.json"
    if not path.exists():
        return SkillLoopPolicy.default()
    return SkillLoopPolicy.load(path)


def policy_path(store: SkillLoopStore) -> Path:
    return store.state_dir / "policy.json"


def evaluations_by_trace(store: SkillLoopStore, traces: list[AgentTrace]) -> dict[str, Evaluation]:
    return store.latest_evaluations({trace.id for trace in traces})


def proposals_by_trace(
    store: SkillLoopStore, traces: list[AgentTrace]
) -> dict[str, list[Proposal]]:
    wanted = {trace.id for trace in traces}
    result = {trace.id: [] for trace in traces}
    for proposal in store.list_proposals(status=None):
        if proposal.trace_id in wanted:
            result[proposal.trace_id].append(proposal)
    return result
