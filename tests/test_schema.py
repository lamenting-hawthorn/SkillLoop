from skillloop.schema import AgentMessage, AgentTrace


def test_trace_round_trip_preserves_messages():
    trace = AgentTrace(
        source="generic",
        messages=[
            AgentMessage(role="user", content="remember I prefer concise answers"),
            AgentMessage(role="assistant", content="Got it."),
        ],
        metadata={"session_id": "abc"},
    )

    restored = AgentTrace.from_dict(trace.to_dict())

    assert restored.source == "generic"
    assert restored.metadata["session_id"] == "abc"
    assert restored.messages[0].role == "user"
    assert restored.messages[0].content == "remember I prefer concise answers"


def test_trace_requires_at_least_one_message():
    try:
        AgentTrace(source="generic", messages=[])
    except ValueError as exc:
        assert "at least one message" in str(exc)
    else:
        raise AssertionError("expected ValueError")
