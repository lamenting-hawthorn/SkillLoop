import json

from skillloop.cli import main


def _write_trace(path, assistant_text="error failed"):
    trace_path = path / "trace.jsonl"
    trace_path.write_text(
        "\n".join(
            [
                json.dumps({"role": "user", "content": "please do the task"}),
                json.dumps({"role": "assistant", "content": assistant_text}),
            ]
        )
    )
    return trace_path


def test_loop_run_evaluates_unevaluated_traces_and_skips_existing(tmp_path, capsys):
    trace_path = _write_trace(tmp_path)
    assert main(["--path", str(tmp_path), "ingest", "generic", str(trace_path)]) == 0

    assert main(["--path", str(tmp_path), "loop", "run", "--min-score", "70"]) == 0
    first = json.loads(capsys.readouterr().out.split("\n", 1)[1])
    assert first["traces_seen"] == 1
    assert first["traces_evaluated"] == 1
    assert first["failing_traces"]

    assert main(["--path", str(tmp_path), "loop", "run", "--min-score", "70"]) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["traces_evaluated"] == 0
    assert second["traces_skipped"] == 1


def test_loop_schedule_status_and_forced_tick(tmp_path, capsys):
    trace_path = _write_trace(tmp_path, assistant_text="Done. Verified with tests.")
    assert main(["--path", str(tmp_path), "ingest", "generic", str(trace_path)]) == 0

    assert (
        main(
            [
                "--path",
                str(tmp_path),
                "loop",
                "schedule",
                "--interval",
                "daily",
                "--condition",
                '{"score_gte":70,"required_tags":["has_final_answer"],"forbidden_tags":["tool_failure"],"max_iterations":3}',
            ]
        )
        == 0
    )
    schedule_output = capsys.readouterr().out
    assert "loop_schedule.json" in schedule_output
    assert (tmp_path / ".skillloop" / "loop_schedule.json").exists()

    assert main(["--path", str(tmp_path), "loop", "status"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["interval"] == "daily"
    assert status["min_score"] == 70
    assert status["condition"]["required_tags"] == ["has_final_answer"]
    assert status["condition"]["forbidden_tags"] == ["tool_failure"]
    assert status["condition"]["max_iterations"] == 3

    assert main(["--path", str(tmp_path), "loop", "tick", "--force"]) == 0
    tick_result = json.loads(capsys.readouterr().out)
    assert tick_result["ran"] is True
    assert tick_result["summary"]["traces_seen"] == 1
    assert tick_result["summary"]["done_traces"]
    evaluation = tick_result["summary"]["evaluations"][0]
    assert evaluation["run_condition"]["result"]["passed"] is True
    assert tick_result["schedule"]["last_run_at"]
    assert tick_result["schedule"]["next_run_at"]

    assert main(["--path", str(tmp_path), "loop", "tick"]) == 0
    not_due = json.loads(capsys.readouterr().out)
    assert not_due["ran"] is False
    assert not_due["summary"] is None


def test_loop_condition_failure_and_max_iterations_stop(tmp_path, capsys):
    trace_path = _write_trace(tmp_path, assistant_text="error failed")
    assert main(["--path", str(tmp_path), "ingest", "generic", str(trace_path)]) == 0

    assert (
        main(
            [
                "--path",
                str(tmp_path),
                "loop",
                "run",
                "--all",
                "--min-score",
                "95",
                "--max-iterations",
                "1",
                "--no-distill-failures",
            ]
        )
        == 0
    )
    first = json.loads(capsys.readouterr().out.split("\n", 1)[1])
    assert first["failing_traces"]
    assert first["stopped_traces"] == []
    assert first["evaluations"][0]["run_condition"]["result"]["should_continue"] is True

    assert (
        main(
            [
                "--path",
                str(tmp_path),
                "loop",
                "run",
                "--all",
                "--min-score",
                "95",
                "--max-iterations",
                "1",
                "--no-distill-failures",
            ]
        )
        == 0
    )
    second = json.loads(capsys.readouterr().out)
    assert second["failing_traces"]
    assert second["stopped_traces"]
    assert second["evaluations"][0]["run_condition"]["result"]["should_continue"] is False
    assert any(
        "max_iterations_exceeded" in reason
        for reason in second["evaluations"][0]["run_condition"]["result"]["reasons"]
    )
