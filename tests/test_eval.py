from skillloop.eval.rubric import evaluate_trace
from skillloop.schema import AgentMessage, AgentTrace


def test_evaluation_rewards_completed_answer():
    trace = AgentTrace(
        source="test",
        messages=[AgentMessage(role="user", content="do x"), AgentMessage(role="assistant", content="Done. Verified with tests.")],
    )

    evaluation = evaluate_trace(trace)

    assert evaluation.score >= 70
    assert "has_final_answer" in evaluation.tags


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
