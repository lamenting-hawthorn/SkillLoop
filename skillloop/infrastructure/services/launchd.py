from __future__ import annotations

import plistlib
import subprocess
from pathlib import Path
from typing import Any

from skillloop.fs_safety import ensure_not_symlink_escape, resolve_under_root
from skillloop.ports.service_manager import ServiceManager, ServiceState
from skillloop.service import (
    DEFAULT_INTERVAL_SECONDS,
    ServiceSpec,
    build_service_spec,
    read_service_metadata,
    validate_launchd_label,
    write_service_metadata,
)


def default_launch_agents_dir() -> Path:
    return Path.home() / "Library" / "LaunchAgents"


def launchd_plist_path(spec: ServiceSpec, launch_agents_dir: str | Path | None = None) -> Path:
    base = (
        Path(launch_agents_dir).expanduser() if launch_agents_dir else default_launch_agents_dir()
    )
    label = validate_launchd_label(spec.label)
    return base / f"{label}.plist"


def launchd_plist(spec: ServiceSpec) -> dict[str, Any]:
    return {
        "Label": spec.label,
        "ProgramArguments": [
            spec.python_executable,
            "-m",
            "skillloop.cli",
            "--path",
            str(spec.project_root),
            "controller",
            "run",
        ],
        "WorkingDirectory": str(spec.project_root),
        "StartInterval": spec.interval_seconds,
        "RunAtLoad": True,
        "StandardOutPath": str(spec.stdout_path),
        "StandardErrorPath": str(spec.stderr_path),
        "EnvironmentVariables": {
            "PYTHONUNBUFFERED": "1",
            **({"PYTHONPATH": spec.python_path} if spec.python_path else {}),
        },
    }


class LaunchdServiceManager(ServiceManager):
    kind = "launchd"

    def install(self, spec: ServiceSpec, *, launch_agents_dir: str | Path | None = None) -> Path:
        ensure_not_symlink_escape(
            spec.state_dir, spec.project_root, label="service state directory"
        )
        spec.state_dir.mkdir(parents=True, exist_ok=True)
        ensure_not_symlink_escape(
            spec.state_dir, spec.project_root, label="service state directory"
        )
        plist_path = launchd_plist_path(spec, launch_agents_dir)
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        with plist_path.open("wb") as fh:
            plistlib.dump(launchd_plist(spec), fh, sort_keys=False)
        write_service_metadata(spec, kind="launchd", path=plist_path)
        return plist_path

    def activate(self, spec: ServiceSpec, *, launch_agents_dir: str | Path | None = None) -> None:
        plist_path = launchd_plist_path(spec, launch_agents_dir)
        subprocess.run(["launchctl", "load", str(plist_path)], check=True)

    def status(
        self, spec: ServiceSpec, *, launch_agents_dir: str | Path | None = None
    ) -> ServiceState:
        plist_path = launchd_plist_path(spec, launch_agents_dir)
        installed = plist_path.exists()
        if not installed:
            return ServiceState(
                kind=self.kind, label=spec.label, installed=False, active=False, path=None
            )
        label = validate_launchd_label(spec.label)
        proc = subprocess.run(
            ["launchctl", "list", label],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return ServiceState(
            kind=self.kind,
            label=label,
            installed=True,
            active=proc.returncode == 0,
            path=str(plist_path),
        )

    def install_message(self, spec: Any, path: str | Path) -> list[str]:
        return [
            f"Wrote launchd service plist to {path}",
            f"label: {spec.label}",
            f"interval_seconds: {spec.interval_seconds}",
            "To start it now, run:",
            f"launchctl bootstrap gui/$(id -u) {path}",
            "To stop it later, run:",
            f"launchctl bootout gui/$(id -u) {path}",
        ]

    def status_message(self, metadata: dict[str, Any]) -> list[str]:
        path = Path(str(metadata.get("path", ""))).expanduser()
        return [
            "SkillLoop service: installed",
            f"kind: {metadata.get('kind')}",
            f"label: {metadata.get('label')}",
            f"path: {path}",
            f"plist_exists: {path.exists()}",
            f"interval_seconds: {metadata.get('interval_seconds')}",
            f"command: {' '.join(str(part) for part in metadata.get('command', []))}",
        ]

    def uninstall(
        self, spec: ServiceSpec, *, launch_agents_dir: str | Path | None = None
    ) -> list[Path]:
        plist_path = launchd_plist_path(spec, launch_agents_dir)
        base = (
            Path(launch_agents_dir).expanduser()
            if launch_agents_dir
            else default_launch_agents_dir()
        )
        expected = resolve_under_root(base, plist_path, label="launchd plist")
        removed: list[Path] = []
        if expected.exists():
            expected.unlink()
            removed.append(expected)
        metadata_path = spec.state_dir / "service.json"
        if metadata_path.exists():
            ensure_not_symlink_escape(metadata_path, spec.state_dir, label="service metadata")
            metadata_path.unlink()
            removed.append(metadata_path)
        return removed


def write_launchd_service(
    spec: ServiceSpec, *, launch_agents_dir: str | Path | None = None
) -> Path:
    return LaunchdServiceManager().install(spec, launch_agents_dir=launch_agents_dir)


def remove_launchd_service(
    *, state_dir: str | Path, launch_agents_dir: str | Path | None = None
) -> list[Path]:
    state_input = Path(state_dir).expanduser()
    state = ensure_not_symlink_escape(
        state_input, state_input.parent, label="service state directory"
    )
    metadata = read_service_metadata(state)
    if not metadata or not metadata.get("label"):
        metadata_path = state / "service.json"
        removed: list[Path] = []
        if metadata_path.exists():
            ensure_not_symlink_escape(metadata_path, state, label="service metadata")
            metadata_path.unlink()
            removed.append(metadata_path)
        return removed
    spec = build_service_spec(
        project_root=metadata.get("project_root") or Path.cwd(),
        state_dir=state,
        label=str(metadata["label"]),
        interval_seconds=int(metadata.get("interval_seconds") or DEFAULT_INTERVAL_SECONDS),
    )
    return LaunchdServiceManager().uninstall(spec, launch_agents_dir=launch_agents_dir)
