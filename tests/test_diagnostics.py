import json

from skillloop.cli import main
from skillloop.diagnostics import run_diagnostics
from skillloop.policy import IngestionPolicy, SkillLoopPolicy
from skillloop.store import SkillLoopStore


def test_diagnostics_are_read_only_for_uninitialized_project(tmp_path):
    checks = run_diagnostics(tmp_path)
    statuses = {check.name: check.status for check in checks}
    assert statuses["database"] == "warn"
    assert statuses["policy"] == "warn"
    assert not (tmp_path / ".skillloop").exists()


def test_diagnostics_validate_initialized_database(tmp_path):
    SkillLoopStore(tmp_path).init()
    assert (
        next(check for check in run_diagnostics(tmp_path) if check.name == "database").status
        == "pass"
    )


def test_diagnostics_fail_for_missing_configured_hermes_database(tmp_path):
    store = SkillLoopStore(tmp_path)
    store.init()
    policy = SkillLoopPolicy.default()
    policy.ingestion = IngestionPolicy(
        enabled=True, adapter="hermes-db", hermes_db_path=str(tmp_path / "missing.db")
    )
    policy.save(store.state_dir / "policy.json")
    assert (
        next(check for check in run_diagnostics(tmp_path) if check.name == "hermes_database").status
        == "fail"
    )


def test_cli_doctor_json_is_machine_readable(tmp_path, capsys):
    assert main(["--path", str(tmp_path), "doctor", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["checks"]


def test_cli_doctor_returns_failure_for_corrupt_database(tmp_path):
    state_dir = tmp_path / ".skillloop"
    state_dir.mkdir()
    (state_dir / "skillloop.db").write_text("not sqlite", encoding="utf-8")
    assert main(["--path", str(tmp_path), "doctor"]) == 1
