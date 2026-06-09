import json
import sqlite3

from skillloop.cli import main


def test_cli_ingest_eval_distill_export_flow(tmp_path, capsys):
    trace_path = tmp_path / "trace.jsonl"
    trace_path.write_text(
        "\n".join(
            [
                json.dumps({"role": "user", "content": "Remember that I prefer concise answers in terminal."}),
                json.dumps({"role": "assistant", "content": "Done. Verified with tests."}),
            ]
        )
    )

    assert main(["--path", str(tmp_path), "init"]) == 0
    assert main(["--path", str(tmp_path), "ingest", "generic", str(trace_path)]) == 0
    assert main(["--path", str(tmp_path), "traces", "list"]) == 0
    assert main(["--path", str(tmp_path), "eval", "latest"]) == 0
    assert main(["--path", str(tmp_path), "distill", "latest"]) == 0
    assert main(["--path", str(tmp_path), "review", "list"]) == 0

    out_path = tmp_path / "data" / "sft.jsonl"
    assert main(["--path", str(tmp_path), "export", "sft", "--out", str(out_path), "--min-score", "70"]) == 0

    lines = out_path.read_text().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["messages"][0]["role"] == "user"
    assert record["metadata"]["trace_id"]
    manifest = json.loads((tmp_path / "data" / "sft.jsonl.manifest.json").read_text())
    assert manifest["records"] == 1
    assert manifest["splits"]["train"]["records"] == 1
    assert manifest["provenance"]["trace_ids"] == [record["metadata"]["trace_id"]]
    output = capsys.readouterr().out
    assert "Ingested" in output
    assert "Created" in output


def test_cli_export_min_score_skips_low_quality_trace(tmp_path):
    trace_path = tmp_path / "trace.jsonl"
    trace_path.write_text(
        "\n".join(
            [
                json.dumps({"role": "user", "content": "do it"}),
                json.dumps({"role": "assistant", "content": "error failed"}),
            ]
        )
    )

    assert main(["--path", str(tmp_path), "ingest", "generic", str(trace_path)]) == 0
    assert main(["--path", str(tmp_path), "eval", "latest"]) == 0
    out_path = tmp_path / "data" / "sft.jsonl"
    assert main(["--path", str(tmp_path), "export", "sft", "--out", str(out_path), "--min-score", "70"]) == 0

    assert out_path.read_text() == ""


def test_cli_ingests_hermes_state_db_latest(tmp_path, capsys):
    db = tmp_path / "state.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT, title TEXT, started_at REAL, ended_at REAL, message_count INTEGER)")
    conn.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, tool_calls TEXT, timestamp REAL, active INTEGER)")
    conn.execute("INSERT INTO sessions VALUES ('s1', 'cli', 'Session', 1.0, NULL, 2)")
    conn.execute("INSERT INTO messages (session_id, role, content, tool_calls, timestamp, active) VALUES ('s1', 'user', 'hello', NULL, 1.1, 1)")
    conn.execute("INSERT INTO messages (session_id, role, content, tool_calls, timestamp, active) VALUES ('s1', 'assistant', 'hi', NULL, 1.2, 1)")
    conn.commit()
    conn.close()

    assert main(["--path", str(tmp_path), "ingest", "hermes-db", "--db-path", str(db), "--latest"]) == 0
    assert main(["--path", str(tmp_path), "traces", "list"]) == 0

    output = capsys.readouterr().out
    assert "hermes_state_db" in output


def test_cli_export_writes_split_files_and_manifest(tmp_path):
    for index in range(4):
        trace_path = tmp_path / f"trace-{index}.jsonl"
        trace_path.write_text(
            "\n".join(
                [
                    json.dumps({"role": "user", "content": f"hello {index}"}),
                    json.dumps({"role": "assistant", "content": "Done. Verified with tests."}),
                ]
            )
        )
        assert main(["--path", str(tmp_path), "ingest", "generic", str(trace_path)]) == 0
        assert main(["--path", str(tmp_path), "eval", "latest"]) == 0

    out_path = tmp_path / "data" / "sft.jsonl"
    manifest_path = tmp_path / "data" / "manifest.json"
    assert main([
        "--path", str(tmp_path), "export", "sft",
        "--out", str(out_path),
        "--manifest-out", str(manifest_path),
        "--splits", "train=0.5,validation=0.25,test=0.25",
        "--min-score", "70",
    ]) == 0

    manifest = json.loads(manifest_path.read_text())
    assert set(manifest["splits"]) == {"train", "validation", "test"}
    assert manifest["records"] == 4
    assert manifest["estimated_tokens"] > 0
    assert (tmp_path / "data" / "sft.train.jsonl").exists()
    assert (tmp_path / "data" / "sft.validation.jsonl").exists()
    assert (tmp_path / "data" / "sft.test.jsonl").exists()


def test_cli_benchmark_writes_report(tmp_path):
    trace_path = tmp_path / "trace.jsonl"
    trace_path.write_text(
        "\n".join(
            [
                json.dumps({"role": "user", "content": "run tests"}),
                json.dumps({"role": "assistant", "content": "Done. Tests passed."}),
            ]
        )
    )
    report_path = tmp_path / "benchmark.json"

    assert main(["--path", str(tmp_path), "ingest", "generic", str(trace_path)]) == 0
    assert main(["--path", str(tmp_path), "benchmark", "--out", str(report_path)]) == 0

    report = json.loads(report_path.read_text())
    assert report["summary"]["traces"] == 1
    assert report["baseline"] == "rubric_legacy"
    assert report["candidates"] == ["rubric"]


def test_cli_training_config_generates_files_without_running_training(tmp_path):
    train = tmp_path / "sft.train.jsonl"
    train.write_text('{"messages":[]}\n')
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"id": "m1", "kind": "sft", "records": 1, "estimated_tokens": 4, "output_files": {"train": str(train)}}))
    config_dir = tmp_path / "configs"

    assert main([
        "--path", str(tmp_path), "training-config", "trl",
        "--dataset-manifest", str(manifest),
        "--base-model", "NousResearch/Test",
        "--output-dir", str(tmp_path / "out"),
        "--config-dir", str(config_dir),
    ]) == 0

    payload = json.loads((config_dir / "trl_sft_config.json").read_text())
    assert payload["safety"]["training_auto_run"] is False
    assert payload["safety"]["execution"] == "config_generation_only"
