from pathlib import Path

import pytest

from skillloop.apply.filesystem import export_approved
from skillloop.review.queue import approve_proposal, reject_proposal
from skillloop.schema import AgentMessage, AgentTrace, Proposal
from skillloop.store import SkillLoopStore


def test_approved_proposals_export_inside_project(tmp_path):
    store = SkillLoopStore(tmp_path)
    trace = AgentTrace(source="test", messages=[AgentMessage(role="user", content="hello")])
    store.save_trace(trace)
    proposal = Proposal(
        trace_id=trace.id,
        kind="memory",
        title="t",
        content="User prefers concise answers",
        reason="r",
        status="approved",
    )
    store.save_proposal(proposal)

    written = export_approved(store)

    assert len(written) == 1
    content = written[0].read_text()
    assert content.startswith("---\n")
    assert "proposal_id:" in content
    assert "source: skillloop_proposal" in content
    assert content.endswith("User prefers concise answers")
    assert Path(written[0]).resolve().is_relative_to(tmp_path.resolve())
    applied = store.get_proposal(proposal.id)
    assert applied.status == "applied"
    assert applied.applied_at is not None


def test_review_queue_can_approve_and_reject(tmp_path):
    store = SkillLoopStore(tmp_path)
    trace = AgentTrace(source="test", messages=[AgentMessage(role="user", content="hello")])
    proposal = Proposal(trace_id=trace.id, kind="memory", title="t", content="c", reason="r")
    store.save_trace(trace)
    store.save_proposal(proposal)

    approved = approve_proposal(store, proposal.id)
    assert approved.status == "approved"

    rejected = reject_proposal(store, proposal.id)
    assert rejected.status == "rejected"


def test_export_rejects_paths_outside_project(tmp_path):
    store = SkillLoopStore(tmp_path)
    store.init()

    with pytest.raises(ValueError):
        export_approved(store, out_dir=tmp_path.parent / "outside")


def test_export_rejects_malicious_proposal_kind(tmp_path):
    store = SkillLoopStore(tmp_path)
    trace = AgentTrace(source="test", messages=[AgentMessage(role="user", content="hello")])
    store.save_trace(trace)
    store.save_proposal(
        Proposal(
            trace_id=trace.id, kind="../x", title="t", content="c", reason="r", status="approved"
        )
    )

    with pytest.raises(ValueError, match="unsupported approved proposal kind"):
        export_approved(store)


def test_export_rejects_malicious_proposal_id(tmp_path):
    store = SkillLoopStore(tmp_path)
    trace = AgentTrace(source="test", messages=[AgentMessage(role="user", content="hello")])
    store.save_trace(trace)
    store.save_proposal(
        Proposal(
            trace_id=trace.id,
            kind="memory",
            id="../x",
            title="t",
            content="c",
            reason="r",
            status="approved",
        )
    )

    with pytest.raises(ValueError, match="proposal id"):
        export_approved(store)


def test_export_rejects_unknown_proposal_kind(tmp_path):
    store = SkillLoopStore(tmp_path)
    trace = AgentTrace(source="test", messages=[AgentMessage(role="user", content="hello")])
    store.save_trace(trace)
    store.save_proposal(
        Proposal(
            trace_id=trace.id, kind="note", title="t", content="c", reason="r", status="approved"
        )
    )

    with pytest.raises(ValueError, match="unsupported approved proposal kind"):
        export_approved(store)


def test_export_rejects_tampered_proposal_content_hash(tmp_path):
    store = SkillLoopStore(tmp_path)
    trace = AgentTrace(source="test", messages=[AgentMessage(role="user", content="hello")])
    store.save_trace(trace)
    proposal = Proposal(
        trace_id=trace.id, kind="memory", title="t", content="c", reason="r", status="approved"
    )
    proposal.content_hash = "bad"
    store.save_proposal(proposal)

    with pytest.raises(ValueError, match="content hash mismatch"):
        export_approved(store)


def test_export_rejects_symlinked_approved_output_dir(tmp_path):
    store = SkillLoopStore(tmp_path)
    store.init()
    outside = tmp_path.parent / f"{tmp_path.name}-approved-outside"
    outside.mkdir()
    approved = tmp_path / ".skillloop" / "approved"
    approved.symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="approved export path"):
        export_approved(store)


def test_duplicate_proposals_are_not_saved_twice(tmp_path):
    store = SkillLoopStore(tmp_path)
    trace = AgentTrace(source="test", messages=[AgentMessage(role="user", content="hello")])
    store.save_trace(trace)
    first = Proposal(trace_id=trace.id, kind="memory", title="one", content="same", reason="r")
    second = Proposal(trace_id=trace.id, kind="memory", title="two", content="same", reason="r")

    first_id = store.save_proposal(first)
    second_id = store.save_proposal(second)

    assert second_id == first_id
    proposals = store.list_proposals(status=None)
    assert len(proposals) == 1
    assert proposals[0].content_hash == first.content_hash


def test_rejected_duplicate_can_be_reproposed(tmp_path):
    store = SkillLoopStore(tmp_path)
    trace = AgentTrace(source="test", messages=[AgentMessage(role="user", content="hello")])
    store.save_trace(trace)
    first = Proposal(
        trace_id=trace.id, kind="memory", title="one", content="same", reason="r", status="rejected"
    )
    second = Proposal(trace_id=trace.id, kind="memory", title="two", content="same", reason="r")

    first_id = store.save_proposal(first)
    second_id = store.save_proposal(second)

    assert first_id != second_id
    assert len(store.list_proposals(status=None)) == 2
