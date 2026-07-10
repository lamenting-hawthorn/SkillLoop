import json

from skillloop.dataset import build_manifest, parse_split_spec, record_stats, split_records
from skillloop.eval.rubric import evaluate_trace
from skillloop.export.sft import export_sft_records
from skillloop.schema import AgentMessage, AgentTrace, Proposal


def test_sft_export_uses_message_format_with_provenance():
    trace = AgentTrace(
        source="test",
        messages=[
            AgentMessage(role="user", content="hello"),
            AgentMessage(role="assistant", content="hi"),
        ],
    )
    evaluation = evaluate_trace(trace)
    proposal = Proposal(trace_id=trace.id, kind="memory", title="t", content="c", reason="r")

    records = export_sft_records(
        [trace],
        evaluations_by_trace={trace.id: evaluation},
        proposals_by_trace={trace.id: [proposal]},
    )

    assert records[0]["messages"] == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]
    assert records[0]["metadata"]["trace_id"] == trace.id
    assert records[0]["metadata"]["evaluation_id"] == evaluation.id
    assert records[0]["metadata"]["proposal_ids"] == [proposal.id]


def test_sft_export_can_omit_metadata_for_plain_training_records():
    trace = AgentTrace(
        source="test",
        messages=[
            AgentMessage(role="user", content="hello"),
            AgentMessage(role="assistant", content="hi"),
        ],
    )

    records = export_sft_records([trace], include_metadata=False)

    assert records == [
        {"messages": [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]}
    ]


def test_split_records_and_stats_are_deterministic():
    records = [
        {"metadata": {"trace_id": str(index)}, "messages": [{"role": "user", "content": "hello"}]}
        for index in range(10)
    ]

    split_a = split_records(records, parse_split_spec("train=0.6,validation=0.2,test=0.2"))
    split_b = split_records(records, parse_split_spec("train=0.6,validation=0.2,test=0.2"))

    assert split_a == split_b
    assert {name: len(items) for name, items in split_a.items()} == {
        "train": 6,
        "validation": 2,
        "test": 2,
    }
    assert record_stats(records)["records"] == 10
    assert record_stats(records)["estimated_tokens"] > 0


def test_manifest_contains_export_metadata_and_provenance(tmp_path):
    trace = AgentTrace(
        source="test",
        messages=[
            AgentMessage(role="user", content="hello"),
            AgentMessage(role="assistant", content="hi"),
        ],
    )
    evaluation = evaluate_trace(trace)
    records = export_sft_records([trace], evaluations_by_trace={trace.id: evaluation})
    split_map = {"train": records}
    output = {"train": tmp_path / "sft.jsonl"}

    manifest = build_manifest(
        kind="sft",
        split_outputs=output,
        split_records_map=split_map,
        source_traces=[trace],
        evaluations_by_trace={trace.id: evaluation},
        export_metadata={"min_score": 70},
    ).to_dict()

    assert manifest["kind"] == "sft"
    assert manifest["records"] == 1
    assert manifest["splits"]["train"]["records"] == 1
    assert manifest["export_metadata"]["min_score"] == 70
    assert manifest["provenance"]["trace_ids"] == [trace.id]
    assert manifest["provenance"]["evaluation_ids"] == [evaluation.id]
    json.dumps(manifest)
