import json
import plistlib

import pytest

from skillloop.cli import main
from skillloop.service import build_service_spec, launchd_plist, read_service_metadata, remove_launchd_service


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
