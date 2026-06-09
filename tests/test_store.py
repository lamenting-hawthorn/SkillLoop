from skillloop.adapters.generic_jsonl import load_generic_jsonl
from skillloop.schema import AgentMessage, AgentTrace, Evaluation, sha256_text
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
    low = Evaluation(trace_id=trace.id, score=40, tags=["error_signal"], created_at="2026-01-01T00:00:00+00:00")
    high = Evaluation(trace_id=trace.id, score=85, tags=["success_signal"], created_at="2026-01-02T00:00:00+00:00")
    store.save_evaluation(low)
    store.save_evaluation(high)

    evaluations = store.list_evaluations(trace.id)

    assert [e.score for e in evaluations] == [85, 40]
    latest = store.latest_evaluation(trace.id)
    assert latest is not None
    assert latest.score == 85


def test_store_preserves_raw_trace_and_hashes(tmp_path):
    raw = tmp_path / "trace.jsonl"
    raw_text = '{"role":"user","content":"hello"}\n'
    raw.write_text(raw_text)
    store = SkillLoopStore(tmp_path)
    trace = load_generic_jsonl(raw)

    trace_id = store.save_trace(trace)
    loaded = store.get_trace(trace_id)

    assert loaded.raw_artifact_ref is not None
    assert loaded.raw_artifact_ref.startswith(".skillloop/raw_traces/")
    assert loaded.raw_trace_sha256 == sha256_text(raw_text)
    assert loaded.normalized_trace_sha256 == loaded.compute_normalized_sha256()
    assert store.read_preserved_raw_trace(loaded) == raw_text
