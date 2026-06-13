import json
import sqlite3

from skillloop.controller import controller_tick
from skillloop.policy import DatasetPolicy, EvaluationPolicy, IngestionPolicy, SkillLoopPolicy
from skillloop.store import SkillLoopStore


def test_controller_tick_ingests_evaluates_exports_and_records_report(tmp_path):
    trace_path = tmp_path / "trace.jsonl"
    trace_path.write_text(
        "\n".join(
            [
                json.dumps({"role": "user", "content": "Remember that I prefer concise summaries."}),
                json.dumps({"role": "assistant", "content": "Done. Verified with tests."}),
            ]
        )
    )
    policy = SkillLoopPolicy(
        ingestion=IngestionPolicy(enabled=True, adapter="generic", paths=[str(trace_path)]),
        evaluation=EvaluationPolicy(min_score=95, only_unevaluated=True, distill_failures=True),
        dataset=DatasetPolicy(enabled=True, kind="sft", out="data/sft.jsonl", min_score=70, splits="train=0.8,validation=0.1,test=0.1"),
    )

    store = SkillLoopStore(tmp_path)
    report = controller_tick(store, policy)

    assert report.summary["errors"] == 0
    assert report.summary["traces_seen"] == 1
    assert report.summary["traces_evaluated"] == 1
    assert report.actions[0]["type"] == "ingest"
    assert report.actions[1]["type"] == "evaluate"
    assert report.actions[2]["type"] == "dataset_export"
    assert report.actions[2]["records"] == 1
    assert (tmp_path / "data" / "sft.train.jsonl").exists()
    assert (tmp_path / "data" / "sft.jsonl.manifest.json").exists()
    run_files = list((tmp_path / ".skillloop" / "controller_runs").glob("*.json"))
    assert len(run_files) == 1
    saved = json.loads(run_files[0].read_text())
    assert saved["id"] == report.id
    stored_runs = store.list_controller_runs()
    assert [run["id"] for run in stored_runs] == [report.id]
    assert store.get_controller_run(report.id[:8])["id"] == report.id
    assert saved["summary"]["requires_review"] >= 1


def test_controller_policy_round_trip(tmp_path):
    policy = SkillLoopPolicy.default()
    path = policy.save(tmp_path / ".skillloop" / "policy.json")

    restored = SkillLoopPolicy.load(path)

    assert restored.mode == "autonomous_review_first"
    assert restored.evaluation.evaluator == "rubric"
    assert restored.training.auto_run is False
    assert restored.training.require_approval is True


def test_controller_ingests_unseen_hermes_sessions_incrementally(tmp_path):
    db = tmp_path / "state.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT, title TEXT, started_at REAL, ended_at REAL, message_count INTEGER)")
    conn.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, tool_calls TEXT, timestamp REAL, active INTEGER)")
    for idx, session_id in enumerate(["s1", "s2"]):
        conn.execute("INSERT INTO sessions VALUES (?, 'cli', ?, ?, NULL, 2)", (session_id, f"Session {session_id}", float(idx + 1)))
        conn.execute("INSERT INTO messages (session_id, role, content, tool_calls, timestamp, active) VALUES (?, 'user', ?, NULL, ?, 1)", (session_id, f"hello {session_id}", float(idx + 1) + 0.1))
        conn.execute("INSERT INTO messages (session_id, role, content, tool_calls, timestamp, active) VALUES (?, 'assistant', 'Done. Verified with tests.', NULL, ?, 1)", (session_id, float(idx + 1) + 0.2))
    conn.commit()
    conn.close()

    policy = SkillLoopPolicy(
        ingestion=IngestionPolicy(enabled=True, adapter="hermes-db", hermes_db_path=str(db), max_sessions=10),
        evaluation=EvaluationPolicy(min_score=70, only_unevaluated=True, distill_failures=True),
    )
    store = SkillLoopStore(tmp_path)

    first = controller_tick(store, policy)
    second = controller_tick(store, policy)

    assert first.actions[0]["type"] == "ingest"
    assert first.actions[0]["count"] == 2
    assert second.actions[0]["count"] == 0
    traces = store.list_traces()
    assert {trace.metadata["session_id"] for trace in traces} == {"s1", "s2"}
