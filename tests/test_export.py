from skillloop.export.sft import export_sft_records
from skillloop.schema import AgentMessage, AgentTrace


def test_sft_export_uses_message_format():
    trace = AgentTrace(
        source="test",
        messages=[AgentMessage(role="user", content="hello"), AgentMessage(role="assistant", content="hi")],
    )

    records = export_sft_records([trace])

    assert records == [{"messages": [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]}]
