from skillloop.distill.memory import propose_memory_updates
from skillloop.distill.skills import propose_skill_updates
from skillloop.schema import AgentMessage, AgentTrace


def test_memory_distiller_finds_user_preference():
    trace = AgentTrace(
        source="test",
        messages=[
            AgentMessage(role="user", content="Remember that I prefer concise answers in terminal.")
        ],
    )

    proposals = propose_memory_updates(trace)

    assert proposals
    assert proposals[0].kind == "memory"
    assert "concise answers" in proposals[0].content


def test_memory_distiller_does_not_mix_workflow_into_preference():
    trace = AgentTrace(
        source="test",
        messages=[
            AgentMessage(
                role="user",
                content="Remember that I prefer concise terminal summaries. When fixing gateway issues, first check logs, then config, then restart.",
            )
        ],
    )

    proposals = propose_memory_updates(trace)

    assert proposals[0].content == "i prefer concise terminal summaries"


def test_skill_distiller_finds_repeated_workflow_signal():
    trace = AgentTrace(
        source="test",
        messages=[
            AgentMessage(
                role="user",
                content="When fixing gateway issues, first check logs, then config, then restart.",
            ),
            AgentMessage(role="assistant", content="I'll save that as a reusable workflow."),
        ],
    )

    proposals = propose_skill_updates(trace)

    assert proposals
    assert proposals[0].kind == "skill"
    assert "gateway" in proposals[0].content.lower()
    assert "Verification" in proposals[0].content
