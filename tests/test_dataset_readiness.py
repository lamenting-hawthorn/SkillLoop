from skillloop.dataset_readiness import DatasetReadinessPolicy, assess_dataset_readiness
from skillloop.eval.rubric import evaluate_trace
from skillloop.export.sft import export_sft_records
from skillloop.schema import AgentMessage, AgentTrace


def _trace(index: int) -> AgentTrace:
    trace = AgentTrace(
        source="test",
        id=f"trace-{index}",
        messages=[
            AgentMessage(role="user", content=f"Please complete task {index}."),
            AgentMessage(role="assistant", content="Done. Verified with tests and documented the result."),
        ],
    )
    trace.normalized_trace_sha256 = trace.compute_normalized_sha256()
    return trace


def test_dataset_readiness_accepts_viable_dataset():
    traces = [_trace(index) for index in range(3)]
    evaluations = {trace.id: evaluate_trace(trace) for trace in traces}
    for evaluation in evaluations.values():
        evaluation.artifact_sha256 = evaluation.compute_artifact_sha256()
    records = export_sft_records(traces, evaluations_by_trace=evaluations)

    report = assess_dataset_readiness(
        split_records_map={"train": records[:2], "validation": records[2:]},
        source_traces=traces,
        evaluations_by_trace=evaluations,
        policy=DatasetReadinessPolicy(min_records=3, min_estimated_tokens=1),
    )

    assert report.ready is True
    assert all(report.checks.values())
    assert report.stats["records"] == 3
    assert report.stats["split_records"] == {"train": 2, "validation": 1}


def test_dataset_readiness_warns_on_too_few_records_and_empty_split():
    trace = _trace(1)
    evaluation = evaluate_trace(trace)
    evaluation.artifact_sha256 = evaluation.compute_artifact_sha256()
    records = export_sft_records([trace], evaluations_by_trace={trace.id: evaluation})

    report = assess_dataset_readiness(
        split_records_map={"train": records, "validation": []},
        source_traces=[trace],
        evaluations_by_trace={trace.id: evaluation},
        policy=DatasetReadinessPolicy(min_records=2, min_estimated_tokens=1),
    )

    assert report.ready is False
    assert report.checks["min_records"] is False
    assert report.checks["non_empty_splits"] is False
    assert "empty dataset splits: validation" in report.warnings


def test_dataset_readiness_flags_missing_metadata_and_hashes():
    trace = AgentTrace(source="test", messages=[AgentMessage(role="user", content="hello")])
    record = {"messages": [{"role": "user", "content": "hello"}]}

    report = assess_dataset_readiness(
        split_records_map={"train": [record]},
        source_traces=[trace],
        evaluations_by_trace={},
        policy=DatasetReadinessPolicy(min_records=1, min_estimated_tokens=1),
    )

    assert report.ready is False
    assert report.checks["metadata"] is False
    assert report.checks["hashes"] is False
