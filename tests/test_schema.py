from skillloop.schema import AgentMessage, AgentTrace, Proposal, ToolCall, TRACE_SCHEMA_VERSION


def test_trace_round_trip_preserves_messages():
    trace = AgentTrace(
        source="generic",
        messages=[
            AgentMessage(role="user", content="remember I prefer concise answers"),
            AgentMessage(role="assistant", content="Got it."),
        ],
        metadata={"session_id": "abc"},
        runtime={"name": "pytest"},
        adapter={"name": "unit", "version": "1.1"},
    )

    restored = AgentTrace.from_dict(trace.to_dict())

    assert restored.source == "generic"
    assert restored.schema_version == TRACE_SCHEMA_VERSION
    assert restored.runtime["name"] == "pytest"
    assert restored.adapter["name"] == "unit"
    assert restored.metadata["session_id"] == "abc"
    assert restored.messages[0].role == "user"
    assert restored.messages[0].content == "remember I prefer concise answers"
    assert restored.normalized_trace_sha256 is not None


def test_trace_requires_at_least_one_message():
    try:
        AgentTrace(source="generic", messages=[])
    except ValueError as exc:
        assert "at least one message" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_old_trace_without_schema_version_still_loads():
    old_payload = {
        "id": "old-trace",
        "source": "generic",
        "created_at": "2026-01-01T00:00:00+00:00",
        "metadata": {"session_id": "abc"},
        "messages": [
            {
                "role": "assistant",
                "content": "Done",
                "tool_calls": [
                    {
                        "name": "terminal",
                        "arguments": {"command": "pytest"},
                        "result": "passed",
                        "success": True,
                    }
                ],
                "metadata": {},
            }
        ],
    }

    trace = AgentTrace.from_dict(old_payload)

    assert trace.schema_version == "1.0"
    assert trace.runtime == {}
    assert trace.adapter == {}
    call = trace.messages[0].tool_calls[0]
    assert call.id
    assert call.status == "success"
    assert call.started_at is None
    assert call.ended_at is None
    assert call.duration_ms is None
    assert call.exit_code is None
    assert call.error_type is None
    assert call.artifact_refs == []


def test_span_ready_tool_call_round_trip():
    call = ToolCall(
        id="call-1",
        name="terminal",
        arguments={"command": "pytest"},
        result="failed",
        success=False,
        started_at="2026-01-01T00:00:00+00:00",
        ended_at="2026-01-01T00:00:01+00:00",
        duration_ms=1000,
        exit_code=1,
        status="error",
        error_type="CommandFailed",
        artifact_refs=[".skillloop/artifacts/test.log"],
    )

    restored = ToolCall.from_dict(call.to_dict())

    assert restored.id == "call-1"
    assert restored.status == "error"
    assert restored.success is False
    assert restored.duration_ms == 1000
    assert restored.exit_code == 1
    assert restored.error_type == "CommandFailed"
    assert restored.artifact_refs == [".skillloop/artifacts/test.log"]


def test_old_proposal_without_lifecycle_metadata_still_loads():
    proposal = Proposal.from_dict(
        {
            "id": "p1",
            "trace_id": "t1",
            "kind": "memory",
            "title": "t",
            "content": "User prefers concise answers",
            "reason": "r",
            "status": "pending",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    )

    assert proposal.content_hash
    assert proposal.applied_at is None
    assert proposal.source_trace_schema_version == "1.0"
    proposal.mark_applied()
    assert proposal.status == "applied"
    assert proposal.applied_at is not None
