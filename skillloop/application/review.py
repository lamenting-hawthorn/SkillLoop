from __future__ import annotations

from skillloop.schema import Proposal
from skillloop.store import SkillLoopStore


class ReviewService:
    def __init__(self, store: SkillLoopStore) -> None:
        self._store = store

    def list_proposals(self, status: str | None, include_all: bool) -> list[Proposal]:
        return self._store.list_proposals(status=None if include_all else status)

    def resolve(self, proposal_ref: str) -> Proposal:
        proposals = self._store.list_proposals(status=None)
        matches = [
            proposal
            for proposal in proposals
            if proposal.id == proposal_ref or proposal.id.startswith(proposal_ref)
        ]
        if not matches:
            raise SystemExit(f"Proposal not found: {proposal_ref}")
        if len(matches) > 1:
            raise SystemExit(f"Proposal id prefix is ambiguous: {proposal_ref}")
        return matches[0]

    def set_status(self, proposal: Proposal, status: str) -> None:
        proposal.status = status
        self._store.save_proposal(proposal)


__all__ = ["ReviewService"]
