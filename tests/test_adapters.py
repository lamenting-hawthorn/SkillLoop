import json

from skillloop.adapters.generic_jsonl import load_generic_jsonl
from skillloop.adapters.hermes import normalize_hermes_export


def test_generic_jsonl_loader_reads_messages(tmp_path):
    path = tmp_path / "trace.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"role": "user", "content": "hello"}),
                json.dumps({"role": "assistant", "content": "hi"}),
            ]
        )
    )

    trace = load_generic_jsonl(path)

    assert trace.source == "generic_jsonl"
    assert [m.role for m in trace.messages] == ["user", "assistant"]


def test_hermes_export_normalizes_messages():
    trace = normalize_hermes_export(
        {
            "session_id": "s1",
            "messages": [
                {"role": "user", "content": "fix this"},
                {"role": "assistant", "content": "done"},
            ],
        }
    )

    assert trace.source == "hermes"
    assert trace.metadata["session_id"] == "s1"
    assert trace.messages[-1].content == "done"
