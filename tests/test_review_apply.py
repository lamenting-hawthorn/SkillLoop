from skillloop.review.queue import approve_proposal, reject_proposal, write_approved_files
from skillloop.schema import AgentMessage, AgentTrace, Proposal
from skillloop.store import SkillLoopStore


def test_review_approve_reject_and_clean_export(tmp_path):
    store = SkillLoopStore(tmp_path)
    trace = AgentTrace(source="test", messages=[AgentMessage(role="user", content="hello")])
    store.save_trace(trace)
    proposal = Proposal(
        trace_id=trace.id,
        kind="memory",
        title="Memory candidate",
        content="User prefers concise answers",
        reason="test",
    )
    store.save_proposal(proposal)

    approved = approve_proposal(store, proposal.id)
    assert approved.status == "approved"

    written = write_approved_files(store)
    assert len(written) == 1
    assert written[0].is_relative_to(tmp_path)
    assert written[0].read_text() == "User prefers concise answers"

    rejected = reject_proposal(store, proposal.id)
    assert rejected.status == "rejected"
