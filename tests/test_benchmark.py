import json

from skillloop.benchmark import replay_benchmark, write_benchmark_report
from skillloop.eval.registry import default_evaluator_registry
from skillloop.schema import AgentMessage, AgentTrace, ToolCall


def test_replay_benchmark_compares_evaluator_versions():
    trace = AgentTrace(
        source="test",
        messages=[
            AgentMessage(role="user", content="run tests"),
            AgentMessage(
                role="assistant",
                content="Done. Tests passed.",
                tool_calls=[ToolCall(name="terminal", arguments={"command": "pytest"}, result="passed", success=True, exit_code=0)],
            ),
        ],
    )

    report = replay_benchmark([trace], default_evaluator_registry(), baseline="rubric_legacy", candidates=["rubric"])
    data = report.to_dict()

    assert data["summary"]["traces"] == 1
    assert data["baseline"] == "rubric_legacy"
    assert data["candidates"] == ["rubric"]
    assert data["cases"][0]["scores"]["rubric"] >= 0
    assert "rubric" in data["cases"][0]["deltas"]
    assert data["cases"][0]["evidence_counts"]["rubric"] > data["cases"][0]["evidence_counts"]["rubric_legacy"]
    assert data["summary"]["evidence_improved_counts"]["rubric"] == 1
    assert data["summary"]["quality_improved_counts"]["rubric"] >= 1
    assert data["summary"]["training_ready_signal"] is True


def test_write_benchmark_report(tmp_path):
    trace = AgentTrace(source="test", messages=[AgentMessage(role="assistant", content="Done.")])
    report = replay_benchmark([trace], default_evaluator_registry())
    out = write_benchmark_report(tmp_path / "benchmark.json", report)

    loaded = json.loads(out.read_text())
    assert loaded["id"] == report.id
    assert loaded["summary"]["traces"] == 1
