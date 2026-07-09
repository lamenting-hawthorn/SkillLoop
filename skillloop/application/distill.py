from __future__ import annotations

from dataclasses import dataclass

from skillloop.distill.memory import propose_memory_updates
from skillloop.distill.skills import propose_skill_updates
from skillloop.loop import proposals_with_provenance
from skillloop.schema import AgentTrace, Evaluation, Proposal
from skillloop.store import SkillLoopStore


@dataclass
class DistillEntry:
    proposal: Proposal
    saved_id: str
    is_new: bool


@dataclass
class DistillResult:
    entries: list[DistillEntry]
    created: list[Proposal]
    duplicates: list[str]


class DistillService:
    def __init__(self, store: SkillLoopStore) -> None:
        self._store = store

    def distill(self, trace: AgentTrace, source_evaluation: Evaluation | None) -> DistillResult:
        proposals = proposals_with_provenance(
            trace.id,
            propose_memory_updates(trace) + propose_skill_updates(trace),
            source_evaluation,
        )
        entries: list[DistillEntry] = []
        created: list[Proposal] = []
        duplicates: list[str] = []
        for proposal in proposals:
            saved_id = self._store.save_proposal(proposal)
            is_new = saved_id == proposal.id
            entries.append(DistillEntry(proposal=proposal, saved_id=saved_id, is_new=is_new))
            if is_new:
                created.append(proposal)
            else:
                duplicates.append(saved_id)
        return DistillResult(entries=entries, created=created, duplicates=duplicates)


__all__ = ["DistillService", "DistillResult"]
