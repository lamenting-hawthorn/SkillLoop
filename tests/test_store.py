import sqlite3

import pytest

from skillloop.adapters.generic_jsonl import load_generic_jsonl
from skillloop.fs_safety import sha256_bytes
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


def test_store_returns_latest_evaluations_in_bulk(tmp_path):
    store = SkillLoopStore(tmp_path)
    first = AgentTrace(source="generic", messages=[AgentMessage(role="user", content="first")])
    second = AgentTrace(source="generic", messages=[AgentMessage(role="user", content="second")])
    store.save_evaluation(Evaluation(trace_id=first.id, score=40, created_at="2026-01-01T00:00:00+00:00"))
    store.save_evaluation(Evaluation(trace_id=first.id, score=90, created_at="2026-01-02T00:00:00+00:00"))
    store.save_evaluation(Evaluation(trace_id=second.id, score=70, created_at="2026-01-01T00:00:00+00:00"))
    latest = store.latest_evaluations({first.id, second.id})
    assert latest[first.id].score == 90
    assert latest[second.id].score == 70


def test_store_migrates_legacy_proposal_table(tmp_path):
    state_dir = tmp_path / ".skillloop"
    state_dir.mkdir()
    with sqlite3.connect(state_dir / "skillloop.db") as connection:
        connection.execute("CREATE TABLE proposals (id TEXT PRIMARY KEY, trace_id TEXT NOT NULL, kind TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL)")
    store = SkillLoopStore(tmp_path)
    store.init()
    with sqlite3.connect(store.db_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(proposals)")}
    assert "content_hash" in columns


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


def test_store_hashes_raw_trace_bytes(tmp_path):
    raw = tmp_path / "trace.bin"
    raw_bytes = b"\xff"
    raw.write_bytes(raw_bytes)
    store = SkillLoopStore(tmp_path)
    trace = AgentTrace(source="generic", messages=[AgentMessage(role="user", content="hello")], raw_artifact_ref=str(raw))

    trace_id = store.save_trace(trace)
    loaded = store.get_trace(trace_id)

    assert loaded.raw_trace_sha256 == sha256_bytes(raw_bytes)
    assert loaded.raw_trace_sha256 != sha256_text(raw_bytes.decode("utf-8", errors="replace"))


def test_store_rejects_malicious_trace_id_for_raw_trace_preservation(tmp_path):
    raw = tmp_path / "trace.jsonl"
    raw.write_text("{}\n")
    store = SkillLoopStore(tmp_path)
    trace = AgentTrace(source="generic", id="../escape", messages=[AgentMessage(role="user", content="hello")], raw_artifact_ref=str(raw))

    with pytest.raises(ValueError, match="trace id"):
        store.save_trace(trace)


def test_store_rejects_symlinked_raw_trace_dir_escape(tmp_path):
    store = SkillLoopStore(tmp_path)
    store.init()
    outside = tmp_path.parent / f"{tmp_path.name}-raw-outside"
    outside.mkdir()
    store.raw_trace_dir.symlink_to(outside, target_is_directory=True)
    raw = tmp_path / "trace.jsonl"
    raw.write_text("{}\n")
    trace = AgentTrace(source="generic", messages=[AgentMessage(role="user", content="hello")], raw_artifact_ref=str(raw))

    with pytest.raises(ValueError, match="raw trace directory"):
        store.save_trace(trace)


def test_store_rejects_symlinked_state_dir_escape(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-state-outside"
    outside.mkdir()
    (tmp_path / ".skillloop").symlink_to(outside, target_is_directory=True)
    store = SkillLoopStore(tmp_path)

    with pytest.raises(ValueError, match="state directory"):
        store.init()


def test_store_rejects_symlinked_raw_trace_dir_escape_before_read(tmp_path):
    store = SkillLoopStore(tmp_path)
    store.init()
    outside = tmp_path.parent / f"{tmp_path.name}-read-raw-outside"
    outside.mkdir()
    store.raw_trace_dir.symlink_to(outside, target_is_directory=True)
    trace = AgentTrace(source="generic", messages=[AgentMessage(role="user", content="hello")], raw_artifact_ref=".skillloop/raw_traces/trace.raw")

    with pytest.raises(ValueError, match="raw trace directory"):
        store.read_preserved_raw_trace(trace)


def test_store_rejects_traversal_raw_artifact_ref_before_read(tmp_path):
    store = SkillLoopStore(tmp_path)
    trace = AgentTrace(source="generic", messages=[AgentMessage(role="user", content="hello")], raw_artifact_ref="../secret.txt")

    with pytest.raises(ValueError, match="preserved raw trace"):
        store.read_preserved_raw_trace(trace)


def test_store_reads_existing_relative_preserved_raw_trace_ref(tmp_path):
    preserved = tmp_path / ".skillloop" / "raw_traces" / "trace.raw"
    preserved.parent.mkdir(parents=True)
    preserved.write_text("hello")
    store = SkillLoopStore(tmp_path)
    trace = AgentTrace(source="generic", messages=[AgentMessage(role="user", content="hello")], raw_artifact_ref=".skillloop/raw_traces/trace.raw")

    assert store.read_preserved_raw_trace(trace) == "hello"


def test_store_validates_controller_run_report_contract(tmp_path):
    store = SkillLoopStore(tmp_path)

    with pytest.raises(ValueError, match="non-empty 'id'"):
        store.save_controller_run({"started_at": "2026-01-01T00:00:00+00:00"})
    with pytest.raises(ValueError, match="non-empty 'started_at'"):
        store.save_controller_run({"id": "run-1"})


def test_store_controller_run_prefix_search_escapes_like_wildcards(tmp_path):
    store = SkillLoopStore(tmp_path)
    store.save_controller_run({"id": "a_b", "started_at": "2026-01-01T00:00:00+00:00"})
    store.save_controller_run({"id": "a1b", "started_at": "2026-01-02T00:00:00+00:00"})

    assert store.get_controller_run("a_")["id"] == "a_b"
