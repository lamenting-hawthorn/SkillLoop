from skillloop.schema import AgentMessage, AgentTrace
from skillloop.store import SkillLoopStore


def test_store_saves_and_loads_trace(tmp_path):
    store = SkillLoopStore(tmp_path)
    store.init()
    trace = AgentTrace(source="generic", messages=[AgentMessage(role="user", content="hello")])

    trace_id = store.save_trace(trace)
    loaded = store.get_trace(trace_id)

    assert loaded.id == trace_id
    assert loaded.messages[0].content == "hello"


def test_store_lists_traces(tmp_path):
    store = SkillLoopStore(tmp_path)
    store.init()
    store.save_trace(AgentTrace(source="a", messages=[AgentMessage(role="user", content="one")]))
    store.save_trace(AgentTrace(source="b", messages=[AgentMessage(role="user", content="two")]))

    traces = store.list_traces()

    assert [t.source for t in traces] == ["b", "a"]
