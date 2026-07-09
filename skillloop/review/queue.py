from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from skillloop.fs_safety import ensure_not_symlink_escape, resolve_under_root, safe_path_segment
from skillloop.schema import Proposal, sha256_text, stable_json_dumps
from skillloop.store import SkillLoopStore

APPROVED_PROPOSAL_KINDS = {"memory": ".md", "skill": ".md"}


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
    base = resolve_under_root(store.root, out_dir or store.state_dir / "approved", label="approved export path")
    ensure_not_symlink_escape(base, store.root, label="approved export path")
    base.mkdir(parents=True, exist_ok=True)
    ensure_not_symlink_escape(base, store.root, label="approved export path")
    written: list[Path] = []
    for proposal in store.list_proposals(status="approved"):
        if proposal.kind not in APPROVED_PROPOSAL_KINDS:
            raise ValueError(f"unsupported approved proposal kind: {proposal.kind}")
        proposal_id = safe_path_segment(proposal.id, label="proposal id")
        expected_hash = sha256_text(stable_json_dumps({"kind": proposal.kind, "content": proposal.content}))
        if proposal.content_hash != expected_hash:
            raise ValueError(f"proposal content hash mismatch: {proposal.id}")
        kind_dir = base / proposal.kind
        kind_dir.mkdir(parents=True, exist_ok=True)
        ensure_not_symlink_escape(kind_dir, store.root, label="approved proposal kind directory")
        path = ensure_not_symlink_escape(kind_dir / f"{proposal_id}{APPROVED_PROPOSAL_KINDS[proposal.kind]}", store.root, label="approved proposal output")
        # Build YAML frontmatter with metadata
        frontmatter_fields = [
            f"proposal_id: {proposal_id}",
            f"trace_id: \"{proposal.trace_id}\"",
        ]
        # Try to get score/evaluator from store evaluations if available
        score = None
        evaluator = None
        try:
            # Look for evaluations linked to this trace
            for ev in store.list_evaluations():
                if ev.trace_id == proposal.trace_id:
                    score = ev.score
                    evaluator = ev.evaluator_name
                    break
        except Exception:
            pass
        if score is not None:
            frontmatter_fields.append(f"score: {score}")
        if evaluator:
            frontmatter_fields.append(f"evaluator: {evaluator}")
        else:
            frontmatter_fields.append("evaluator: rubric")
        frontmatter_fields.append("suggested_memory_type: unknown")
        frontmatter_fields.append("suggested_category: unknown")
        frontmatter_fields.append("source: skillloop_proposal")
        frontmatter_fields.append(f"created_at: {datetime.now(timezone.utc).isoformat()}")

        frontmatter = "---\n" + "\n".join(frontmatter_fields) + "\n---\n"
        path.write_text(frontmatter + proposal.content, encoding="utf-8")
        proposal.mark_applied()
        store.save_proposal(proposal)
        written.append(path)
    return written
