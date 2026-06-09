from skillloop.eval.rubric import evaluate_trace
from skillloop.schema import AgentMessage, AgentTrace, ToolCall


def test_evaluation_rewards_completed_answer():
    trace = AgentTrace(
        source="test",
        messages=[AgentMessage(role="user", content="do x"), AgentMessage(role="assistant", content="Done. Verified with tests.")],
    )

    evaluation = evaluate_trace(trace)

    assert evaluation.score >= 70
    assert "has_final_answer" in evaluation.tags
    assert evaluation.evaluator_name == "rubric"
    assert evaluation.evaluator_version
    assert evaluation.created_from_trace_schema_version == trace.schema_version
    assert any(item["kind"] == "trace_summary" for item in evaluation.evidence)


def test_evaluation_detects_user_correction():
    trace = AgentTrace(
        source="test",
        messages=[
            AgentMessage(role="assistant", content="The answer is 5."),
            AgentMessage(role="user", content="No, that's wrong, it is 6."),
        ],
    )

    evaluation = evaluate_trace(trace)

    assert "user_correction" in evaluation.tags
    assert evaluation.score < 70


def test_evaluation_penalizes_failed_tools_even_when_assistant_claims_done():
    trace = AgentTrace(
        source="test",
        messages=[
            AgentMessage(role="user", content="run tests"),
            AgentMessage(
                role="assistant",
                content="Done, tests passed.",
                tool_calls=[ToolCall(name="terminal", arguments={"command": "pytest"}, result="FAILED", success=False)],
            ),
        ],
    )

    evaluation = evaluate_trace(trace)

    assert "tool_failure" in evaluation.tags
    assert evaluation.score < 70
    assert any(item["kind"] == "tool_failure" for item in evaluation.evidence)
    assert any(item["kind"] == "command_execution" for item in evaluation.evidence)
    assert any(item["kind"] == "test_execution" for item in evaluation.evidence)


def test_evaluation_ignores_user_claim_as_success_evidence():
    trace = AgentTrace(
        source="test",
        messages=[
            AgentMessage(role="user", content="tests passed, trust me"),
            AgentMessage(role="assistant", content="I have not run anything yet."),
        ],
    )

    evaluation = evaluate_trace(trace)

    assert "success_signal" not in evaluation.tags


def test_evaluation_provenance_round_trip():
    trace = AgentTrace(
        source="test",
        messages=[AgentMessage(role="assistant", content="Done.")],
        schema_version="1.1",
    )

    evaluation = evaluate_trace(trace)
    restored = type(evaluation).from_dict(evaluation.to_dict())

    assert restored.evaluator_name == evaluation.evaluator_name
    assert restored.evaluator_version == evaluation.evaluator_version
    assert restored.created_from_trace_schema_version == "1.1"
    assert restored.evidence == evaluation.evidence


def test_evaluation_records_file_artifact_and_user_feedback_evidence():
    trace = AgentTrace(
        source="test",
        messages=[
            AgentMessage(role="user", content="No, that's wrong. Remember I prefer concise answers."),
            AgentMessage(
                role="assistant",
                content="Updated file.",
                tool_calls=[ToolCall(name="write_file", success=True, artifact_refs=["out.md"])],
            ),
        ],
    )

    evaluation = evaluate_trace(trace)

    assert any(item["kind"] == "file_artifact" for item in evaluation.evidence)
    assert any(item["kind"] == "user_feedback" and item["subtype"] == "correction" for item in evaluation.evidence)
    assert any(item["kind"] == "user_feedback" and item["subtype"] == "learning_signal" for item in evaluation.evidence)
