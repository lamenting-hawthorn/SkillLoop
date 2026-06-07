import json

from skillloop.adapters.generic_jsonl import load_generic_jsonl
from skillloop.export.dpo import export_dpo_records
from skillloop.export.sft import export_sft_records
from skillloop.schema import AgentMessage, AgentTrace


def test_generic_ingest_redacts_secret_text(tmp_path):
    path = tmp_path / "trace.jsonl"
    path.write_text(json.dumps({"role": "user", "content": "my key is sk-abc...3456"}))

    trace = load_generic_jsonl(path)

    assert "sk-abc...3456" not in trace.messages[0].content
    assert "[REDACTED_SECRET]" in trace.messages[0].content


def test_sft_export_redacts_secret_text():
    trace = AgentTrace(
        source="test",
        messages=[
            AgentMessage(role="user", content="key sk-abc...3456"),
            AgentMessage(role="assistant", content="done"),
        ],
    )

    records = export_sft_records([trace])

    assert "sk-abc...3456" not in json.dumps(records)
    assert "[REDACTED_SECRET]" in json.dumps(records)


def test_dpo_export_redacts_secret_text():
    trace = AgentTrace(
        source="test",
        messages=[AgentMessage(role="user", content="hello")],
        metadata={"dpo_pair": {"prompt": "key sk-abc...3456", "chosen": "safe", "rejected": "bad"}},
    )

    records = export_dpo_records([trace])

    assert "sk-abc...3456" not in json.dumps(records)
    assert "[REDACTED_SECRET]" in json.dumps(records)
