import json
import plistlib
from pathlib import Path
from unittest import mock

import pytest

from skillloop.cli import main
from skillloop.service import (
    build_service_spec,
    launchd_plist,
    read_service_metadata,
    remove_launchd_service,
)
from skillloop.infrastructure.services import get_service_manager
from skillloop.infrastructure.services.systemd import SystemdServiceManager, systemd_unit
from skillloop.ports.service_manager import ServiceState


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
    assert payload["EnvironmentVariables"]["PYTHONUNBUFFERED"] == "1"
    assert payload["EnvironmentVariables"]["PYTHONPATH"]


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
    assert metadata["python_path"]

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


def test_service_uninstall_ignores_tampered_metadata_path(tmp_path):
    launch_agents = tmp_path / "LaunchAgents"
    assert main([
        "--path", str(tmp_path),
        "service", "install",
        "--kind", "launchd",
        "--label", "com.skillloop.test",
        "--launch-agents-dir", str(launch_agents),
    ]) == 0
    plist_path = launch_agents / "com.skillloop.test.plist"
    outside = tmp_path.parent / f"{tmp_path.name}-outside.plist"
    outside.write_text("do not delete")
    metadata_path = tmp_path / ".skillloop" / "service.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["path"] = str(outside)
    metadata_path.write_text(json.dumps(metadata))

    removed = remove_launchd_service(state_dir=tmp_path / ".skillloop", launch_agents_dir=launch_agents)

    assert not plist_path.exists()
    assert outside.exists()
    assert outside not in removed
    assert not metadata_path.exists()


def test_service_install_rejects_symlinked_state_dir_escape(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-service-state-outside"
    outside.mkdir()
    state_dir = tmp_path / ".skillloop"
    state_dir.symlink_to(outside, target_is_directory=True)
    spec = build_service_spec(project_root=tmp_path, state_dir=state_dir, label="com.skillloop.test")

    with pytest.raises(ValueError, match="state directory"):
        main([
            "--path", str(tmp_path),
            "service", "install",
            "--kind", "launchd",
            "--label", spec.label,
            "--launch-agents-dir", str(tmp_path / "LaunchAgents"),
        ])


def test_service_uninstall_rejects_symlinked_state_dir_escape(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-service-uninstall-outside"
    outside.mkdir()
    state_dir = tmp_path / ".skillloop"
    state_dir.symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="service state directory"):
        remove_launchd_service(state_dir=state_dir, launch_agents_dir=tmp_path / "LaunchAgents")


@pytest.mark.parametrize("label", ["../bad", "com.skillloop..bad"])
def test_service_rejects_invalid_labels(tmp_path, label):
    with pytest.raises(ValueError, match="service label"):
        build_service_spec(project_root=tmp_path, state_dir=tmp_path / ".skillloop", label=label)


def test_systemd_unit_runs_controller_tick(tmp_path):
    spec = build_service_spec(
        project_root=tmp_path,
        state_dir=tmp_path / ".skillloop",
        interval_seconds=900,
        label="com.skillloop.test",
        python_executable="/usr/bin/python3",
    )

    unit = systemd_unit(spec)

    assert "[Unit]" in unit and "[Service]" in unit and "[Install]" in unit
    assert "WantedBy=default.target" in unit
    assert "ExecStart=/usr/bin/python3 -m skillloop.cli --path" in unit
    assert "WorkingDirectory=" in unit
    assert str(spec.project_root) in unit.split("WorkingDirectory=")[1].splitlines()[0]


def test_systemd_install_status_activate_uninstall_parity(tmp_path, monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd, *a, **k):
        calls.append(list(cmd))
        proc = mock.Mock()
        proc.returncode = 0
        return proc

    monkeypatch.setattr("skillloop.infrastructure.services.systemd.subprocess.run", fake_run)

    spec = build_service_spec(
        project_root=tmp_path,
        state_dir=tmp_path / ".skillloop",
        interval_seconds=600,
        label="com.skillloop.test",
        python_executable="/usr/bin/python3",
    )
    user_dir = tmp_path / "systemd" / "user"
    mgr = SystemdServiceManager()

    unit_path = mgr.install(spec, launch_agents_dir=user_dir)
    assert unit_path.exists()
    assert unit_path.name == "com.skillloop.test.service"
    assert unit_path.parent == user_dir

    metadata = read_service_metadata(tmp_path / ".skillloop")
    assert metadata["kind"] == "systemd"
    assert metadata["path"] == str(unit_path)

    # install must NOT auto-activate
    assert not any("systemctl" in c for c in calls)

    mgr.activate(spec, launch_agents_dir=user_dir)
    assert ["systemctl", "--user", "daemon-reload"] in calls
    assert ["systemctl", "--user", "enable", "--now", "com.skillloop.test.service"] in calls

    state = mgr.status(spec, launch_agents_dir=user_dir)
    assert isinstance(state, ServiceState)
    assert state.kind == "systemd" and state.installed and state.active

    removed = mgr.uninstall(spec, launch_agents_dir=user_dir)
    assert unit_path not in removed or not unit_path.exists()
    assert not unit_path.exists()
    assert not (tmp_path / ".skillloop" / "service.json").exists()
    assert ["systemctl", "--user", "disable", "com.skillloop.test.service"] in calls


def test_service_manager_factory_exposes_both_kinds():
    assert get_service_manager("launchd").kind == "launchd"
    assert get_service_manager("systemd").kind == "systemd"
    with pytest.raises(ValueError):
        get_service_manager("windows-task-scheduler")
