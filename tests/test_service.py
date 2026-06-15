import json
import plistlib

import pytest

from skillloop.cli import main
from skillloop.service import build_service_spec, launchd_plist, read_service_metadata


def test_launchd_plist_runs_controller_tick(tmp_path):
    spec = build_service_spec(
        project_root=tmp_path,
        state_dir=tmp_path / ".skillloop",
        interval_seconds=900,
        label="com.skillloop.test",
        python_executable="/usr/bin/python3",
    )

    payload = launchd_plist(spec)

    assert payload["Label"] == "com.skillloop.test"
    assert payload["StartInterval"] == 900
    assert payload["RunAtLoad"] is True
    assert payload["WorkingDirectory"] == str(tmp_path.resolve())
    assert payload["ProgramArguments"] == [
        "/usr/bin/python3",
        "-m",
        "skillloop.cli",
        "--path",
        str(tmp_path.resolve()),
        "controller",
        "run",
    ]


def test_service_install_status_and_uninstall_cli(tmp_path, capsys):
    launch_agents = tmp_path / "LaunchAgents"

    assert main([
        "--path", str(tmp_path),
        "service", "install",
        "--kind", "launchd",
        "--label", "com.skillloop.test",
        "--interval-seconds", "300",
        "--launch-agents-dir", str(launch_agents),
    ]) == 0

    plist_path = launch_agents / "com.skillloop.test.plist"
    assert plist_path.exists()
    with plist_path.open("rb") as fh:
        plist = plistlib.load(fh)
    assert plist["Label"] == "com.skillloop.test"
    assert plist["StartInterval"] == 300

    metadata = read_service_metadata(tmp_path / ".skillloop")
    assert metadata is not None
    assert metadata["kind"] == "launchd"
    assert metadata["label"] == "com.skillloop.test"
    assert metadata["path"] == str(plist_path)

    assert main(["--path", str(tmp_path), "service", "status"]) == 0
    assert main(["--path", str(tmp_path), "service", "status", "--json"]) == 0
    output = capsys.readouterr().out
    assert "SkillLoop service: installed" in output
    assert '"label": "com.skillloop.test"' in output

    assert main([
        "--path", str(tmp_path),
        "service", "uninstall",
        "--launch-agents-dir", str(launch_agents),
    ]) == 0

    assert not plist_path.exists()
    assert not (tmp_path / ".skillloop" / "service.json").exists()


def test_service_install_rejects_invalid_interval(tmp_path):
    with pytest.raises(SystemExit, match="--interval-seconds must be positive"):
        main([
            "--path", str(tmp_path),
            "service", "install",
            "--kind", "launchd",
            "--interval-seconds", "0",
        ])
