import json

from skillloop.cli import main
from skillloop.store import SkillLoopStore


def test_e2e_pipeline_smoke(tmp_path, capsys):
    """Full pipeline: init → ingest → eval → distill → review approve → apply → export SFT."""
    project = tmp_path / "project"
    project.mkdir()
    data_dir = project / "data"
    data_dir.mkdir()

    trace_file = data_dir / "trace.jsonl"
    trace_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "role": "user",
                        "content": "Remember that I prefer concise answers in terminal.",
                    }
                ),
                json.dumps(
                    {"role": "assistant", "content": "Done. Verified with tests."},
                ),
            ]
        )
        + "\n"
    )

    assert main(["--path", str(project), "init"]) == 0

    assert main(["--path", str(project), "ingest", "generic", str(trace_file)]) == 0

    assert main(["--path", str(project), "eval", "latest"]) == 0

    assert main(["--path", str(project), "distill", "latest"]) == 0

    assert main(["--path", str(project), "review", "list"]) == 0

    store = SkillLoopStore(project)
    proposals = store.list_proposals(status="pending")
    assert proposals, "expected at least one pending proposal after distill"
    pid = proposals[0].id
    assert main(["--path", str(project), "review", "approve", pid]) == 0

    assert main(["--path", str(project), "apply"]) == 0

    out_path = data_dir / "sft.jsonl"
    assert (
        main(
            [
                "--path",
                str(project),
                "export",
                "sft",
                "--out",
                str(out_path),
                "--min-score",
                "70",
            ]
        )
        == 0
    )

    assert out_path.exists()
    assert out_path.stat().st_size > 0

    lines = out_path.read_text().splitlines()
    assert len(lines) >= 1
    record = json.loads(lines[0])
    assert "messages" in record
    assert record["messages"][0]["role"] == "user"

    manifest_path = project / "data" / "sft.jsonl.manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text())
    assert manifest["records"] >= 1

    capsys.readouterr()
