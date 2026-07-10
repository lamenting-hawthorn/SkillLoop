import json

import pytest

from skillloop.cli import build_parser, main


def _registered_flags(parser):
    return {action.option_strings[0] for action in parser._actions if action.option_strings}


def test_cli_init_subcommand_exists():
    parser = build_parser()
    subparsers = next(a for a in parser._actions if a.dest == "command")
    assert "init" in subparsers.choices


def test_cli_doctor_subcommand_exists():
    parser = build_parser()
    subparsers = next(a for a in parser._actions if a.dest == "command")
    assert "doctor" in subparsers.choices


def test_cli_path_is_global_flag():
    parser = build_parser()
    flags = _registered_flags(parser)
    assert "--path" in flags


def test_cli_ingest_accepts_adapter_positional_and_flags():
    parser = build_parser()
    subparsers = next(a for a in parser._actions if a.dest == "command")
    ingest = subparsers.choices["ingest"]
    flags = _registered_flags(ingest)
    for flag in ("--db-path", "--latest", "--session-id"):
        assert flag in flags, f"ingest missing {flag}"


def test_cli_export_accepts_format_positional_and_flags():
    parser = build_parser()
    subparsers = next(a for a in parser._actions if a.dest == "command")
    export = subparsers.choices["export"]
    flags = _registered_flags(export)
    for flag in ("--out", "--min-score", "--splits", "--manifest-out", "--trace-id"):
        assert flag in flags, f"export missing {flag}"


def test_cli_ingest_rejects_missing_input(tmp_path):
    with pytest.raises(SystemExit):
        main(["--path", str(tmp_path), "ingest", "generic"])


def test_cli_init_and_export_with_min_score(tmp_path):
    trace_file = tmp_path / "trace.jsonl"
    trace_file.write_text(
        "\n".join(
            [
                json.dumps({"role": "user", "content": "Remember X."}),
                json.dumps({"role": "assistant", "content": "Done."}),
            ]
        )
        + "\n"
    )
    main(["--path", str(tmp_path), "init"])
    main(["--path", str(tmp_path), "ingest", "generic", str(trace_file)])
    main(["--path", str(tmp_path), "eval", "latest"])
    out = tmp_path / "out.jsonl"
    assert (
        main(["--path", str(tmp_path), "export", "sft", "--out", str(out), "--min-score", "70"])
        == 0
    )
    assert out.exists()
