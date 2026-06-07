from skillloop.schema import AgentMessage, AgentTrace, Evaluation
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


def test_store_lists_evaluations_for_trace(tmp_path):
    store = SkillLoopStore(tmp_path)
    trace = AgentTrace(source="generic", messages=[AgentMessage(role="user", content="hello")])
    store.save_trace(trace)
    low = Evaluation(trace_id=trace.id, score=40, tags=["error_signal"])
    high = Evaluation(trace_id=trace.id, score=85, tags=["success_signal"])
    store.save_evaluation(low)
    store.save_evaluation(high)

    evaluations = store.list_evaluations(trace.id)

    assert [e.score for e in evaluations] == [85, 40]
