from __future__ import annotations

from pathlib import Path

from skillloop.schema import Proposal
from skillloop.store import SkillLoopStore


def list_pending(store: SkillLoopStore) -> list[Proposal]:
    return store.list_proposals(status="pending")


def approve_proposal(store: SkillLoopStore, proposal_id: str) -> Proposal:
    proposal = store.get_proposal(proposal_id)
    if proposal.status == "applied":
        return proposal
    proposal.status = "approved"
    store.save_proposal(proposal)
    return proposal


def reject_proposal(store: SkillLoopStore, proposal_id: str) -> Proposal:
    proposal = store.get_proposal(proposal_id)
    proposal.status = "rejected"
    store.save_proposal(proposal)
    return proposal


def write_approved_files(store: SkillLoopStore, out_dir: str | Path | None = None) -> list[Path]:
    """Write approved proposal content under project .skillloop/approved.

    This deliberately does not mutate Hermes memory/skills. It creates clean export
    artifacts that can be inspected, committed, or imported elsewhere.
    """
    base = Path(out_dir) if out_dir is not None else store.state_dir / "approved"
    base = base.resolve()
    store_root = store.root.resolve()
    try:
        base.relative_to(store_root)
    except ValueError as exc:
        raise ValueError(f"approved export path must stay under project root: {base}") from exc

    base.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for proposal in store.list_proposals(status="approved"):
        kind_dir = base / proposal.kind
        kind_dir.mkdir(parents=True, exist_ok=True)
        suffix = ".md" if proposal.kind in {"memory", "skill"} else ".txt"
        path = kind_dir / f"{proposal.id}{suffix}"
        path.write_text(proposal.content, encoding="utf-8")
        proposal.mark_applied()
        store.save_proposal(proposal)
        written.append(path)
    return written
