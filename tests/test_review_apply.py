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
    proposal = Proposal(trace_id=trace.id, kind="memory", title="t", content="User prefers concise answers", reason="r", status="approved")
    store.save_proposal(proposal)

    written = export_approved(store)

    assert len(written) == 1
    assert written[0].read_text() == "User prefers concise answers"
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
    first = Proposal(trace_id=trace.id, kind="memory", title="one", content="same", reason="r", status="rejected")
    second = Proposal(trace_id=trace.id, kind="memory", title="two", content="same", reason="r")

    first_id = store.save_proposal(first)
    second_id = store.save_proposal(second)

    assert first_id != second_id
    assert len(store.list_proposals(status=None)) == 2
