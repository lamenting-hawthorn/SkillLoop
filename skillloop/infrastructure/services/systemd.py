from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from skillloop.fs_safety import ensure_not_symlink_escape, safe_path_segment
from skillloop.ports.service_manager import ServiceManager, ServiceState
from skillloop.service import (
    ServiceSpec,
    write_service_metadata,
)


def default_systemd_user_dir() -> Path:
    return Path.home() / ".config" / "systemd" / "user"


def validate_unit_name(label: str) -> str:
    safe = safe_path_segment(label, label="service label")
    if any(part in {"", ".", ".."} for part in safe.split(".")):
        raise ValueError("service label must not contain traversal segments")
    return safe


def systemd_unit_path(spec: ServiceSpec, systemd_user_dir: str | Path | None = None) -> Path:
    base = Path(systemd_user_dir).expanduser() if systemd_user_dir else default_systemd_user_dir()
    return base / f"{validate_unit_name(spec.label)}.service"


def systemd_unit(spec: ServiceSpec) -> str:
    env = "PYTHONUNBUFFERED=1"
    if spec.python_path:
        env = f"{env}\nEnvironment=PYTHONPATH={spec.python_path}"
    return (
        "[Unit]\n"
        "Description=SkillLoop controller service\n"
        "After=network.target\n"
        "\n"
        "[Service]\n"
        f"Type=simple\n"
        f"WorkingDirectory={spec.project_root}\n"
        f"ExecStart={spec.python_executable} -m skillloop.cli --path {spec.project_root} controller run\n"
        f"Environment={env}\n"
        f"StandardOutput=append:{spec.stdout_path}\n"
        f"StandardError=append:{spec.stderr_path}\n"
        "\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )


class SystemdServiceManager(ServiceManager):
    kind = "systemd"

    def install(self, spec: ServiceSpec, *, launch_agents_dir: str | Path | None = None) -> Path:
        ensure_not_symlink_escape(
            spec.state_dir, spec.project_root, label="service state directory"
        )
        spec.state_dir.mkdir(parents=True, exist_ok=True)
        ensure_not_symlink_escape(
            spec.state_dir, spec.project_root, label="service state directory"
        )
        unit_path = systemd_unit_path(spec, launch_agents_dir)
        unit_path.parent.mkdir(parents=True, exist_ok=True)
        unit_path.write_text(systemd_unit(spec), encoding="utf-8")
        write_service_metadata(spec, kind="systemd", path=unit_path)
        return unit_path

    def activate(self, spec: ServiceSpec, *, launch_agents_dir: str | Path | None = None) -> None:
        unit_path = systemd_unit_path(spec, launch_agents_dir)
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(
            ["systemctl", "--user", "enable", "--now", unit_path.name],
            check=True,
        )

    def status(
        self, spec: ServiceSpec, *, launch_agents_dir: str | Path | None = None
    ) -> ServiceState:
        unit_path = systemd_unit_path(spec, launch_agents_dir)
        installed = unit_path.exists()
        if not installed:
            return ServiceState(
                kind=self.kind, label=spec.label, installed=False, active=False, path=None
            )
        enabled = (
            subprocess.run(
                ["systemctl", "--user", "is-enabled", unit_path.name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            ).returncode
            == 0
        )
        active = (
            subprocess.run(
                ["systemctl", "--user", "is-active", unit_path.name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            ).returncode
            == 0
        )
        return ServiceState(
            kind=self.kind,
            label=spec.label,
            installed=True,
            active=enabled and active,
            path=str(unit_path),
        )

    def install_message(self, spec: Any, path: str | Path) -> list[str]:
        unit_name = Path(path).name
        return [
            f"Wrote systemd service unit to {path}",
            f"label: {spec.label}",
            f"interval_seconds: {spec.interval_seconds}",
            "To start it now, run:",
            f"systemctl --user enable --now {unit_name}",
            "To stop it later, run:",
            f"systemctl --user disable --now {unit_name}",
        ]

    def status_message(self, metadata: dict[str, Any]) -> list[str]:
        path = Path(str(metadata.get("path", ""))).expanduser()
        return [
            "SkillLoop service: installed",
            f"kind: {metadata.get('kind')}",
            f"label: {metadata.get('label')}",
            f"path: {path}",
            f"unit_exists: {path.exists()}",
            f"interval_seconds: {metadata.get('interval_seconds')}",
            f"command: {' '.join(str(part) for part in metadata.get('command', []))}",
        ]

    def uninstall(
        self, spec: ServiceSpec, *, launch_agents_dir: str | Path | None = None
    ) -> list[Path]:
        unit_path = systemd_unit_path(spec, launch_agents_dir)
        subprocess.run(
            ["systemctl", "--user", "disable", unit_path.name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        removed: list[Path] = []
        if unit_path.exists():
            unit_path.unlink()
            removed.append(unit_path)
        metadata_path = spec.state_dir / "service.json"
        if metadata_path.exists():
            ensure_not_symlink_escape(metadata_path, spec.state_dir, label="service metadata")
            metadata_path.unlink()
            removed.append(metadata_path)
        subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return removed
