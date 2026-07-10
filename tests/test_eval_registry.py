from skillloop.eval.registry import (
    EvaluatorRegistry,
    RegisteredEvaluator,
    default_evaluator_registry,
)
from skillloop.schema import AgentMessage, AgentTrace, Evaluation


def test_default_registry_exposes_rubric():
    registry = default_evaluator_registry()

    assert registry.names() == ["rubric", "rubric_legacy"]


def test_registry_evaluates_trace():
    registry = default_evaluator_registry()
    trace = AgentTrace(source="test", messages=[AgentMessage(role="assistant", content="Done")])

    evaluation = registry.evaluate(trace, "rubric")

    assert evaluation.evaluator_name == "rubric"
    assert evaluation.score >= 70
    assert evaluation.component_provenance["kind"] == "evaluator"
    assert evaluation.component_provenance["name"] == "rubric"
    assert evaluation.component_provenance["component_sha256"]
    assert evaluation.artifact_sha256


def test_registry_fills_missing_evaluator_identity():
    registry = EvaluatorRegistry()

    def fake(trace: AgentTrace) -> Evaluation:
        return Evaluation(
            trace_id=trace.id, score=1, evaluator_name="unknown", evaluator_version="0"
        )

    registry.register(RegisteredEvaluator(name="fake", version="2", evaluate=fake))
    trace = AgentTrace(source="test", messages=[AgentMessage(role="assistant", content="x")])

    evaluation = registry.evaluate(trace, "fake")

    assert evaluation.evaluator_name == "fake"
    assert evaluation.evaluator_version == "2"
