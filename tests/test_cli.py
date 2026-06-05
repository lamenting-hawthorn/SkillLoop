from pathlib import Path

from skillloop.cli import main


def test_cli_end_to_end_clean_export(tmp_path):
    trace_path = tmp_path / "trace.jsonl"
    trace_path.write_text(
        '\n'.join([
            '{"role":"user","content":"Remember that I prefer concise answers."}',
            '{"role":"user","content":"When debugging tests, first reproduce, then patch."}',
            '{"role":"assistant","content":"Done and verified."}',
        ])
    )

    assert main(["--path", str(tmp_path), "init"]) == 0
    assert main(["--path", str(tmp_path), "ingest", "generic", str(trace_path)]) == 0
    assert main(["--path", str(tmp_path), "traces", "list"]) == 0
    assert main(["--path", str(tmp_path), "eval", "latest"]) == 0
    assert main(["--path", str(tmp_path), "distill", "latest"]) == 0

    proposals = list((tmp_path / ".skillloop").glob("**/*"))
    assert proposals

    sft_out = tmp_path / "data" / "sft.jsonl"
    assert main(["--path", str(tmp_path), "export", "sft", "--out", str(sft_out)]) == 0
    assert sft_out.exists()
    assert '"messages"' in sft_out.read_text()
