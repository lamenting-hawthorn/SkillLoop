from __future__ import annotations

import hashlib
import json
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from skillloop.fs_safety import ensure_not_symlink_escape, resolve_under_root, safe_path_segment

SERVICE_VERSION = "1.0"
DEFAULT_INTERVAL_SECONDS = 3600


@dataclass(frozen=True)
class ServiceSpec:
    label: str
    project_root: Path
    state_dir: Path
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS
    python_executable: str = sys.executable
    python_path: str | None = None

    @property
    def stdout_path(self) -> Path:
        return self.state_dir / "service.out.log"

    @property
    def stderr_path(self) -> Path:
        return self.state_dir / "service.err.log"

    @property
    def metadata_path(self) -> Path:
        return self.state_dir / "service.json"


def default_label(project_root: str | Path) -> str:
    root = Path(project_root).expanduser().resolve()
    digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:12]
    return f"com.skillloop.controller.{digest}"


def validate_launchd_label(label: str) -> str:
    safe = safe_path_segment(label, label="service label")
    if any(part in {"", ".", ".."} for part in safe.split(".")):
        raise ValueError("service label must not contain traversal segments")
    return safe


def build_service_spec(
    *,
    project_root: str | Path,
    state_dir: str | Path,
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    label: str | None = None,
    python_executable: str | None = None,
) -> ServiceSpec:
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be positive")
    root = Path(project_root).expanduser().resolve()
    state = Path(state_dir).expanduser().resolve()
    service_label = validate_launchd_label(label or default_label(root))
    return ServiceSpec(
        label=service_label,
        project_root=root,
        state_dir=state,
        interval_seconds=interval_seconds,
        python_executable=python_executable or sys.executable,
        python_path=str(Path(__file__).resolve().parents[1]),
    )


def write_service_metadata(spec: ServiceSpec, *, kind: str, path: str | Path) -> Path:
    ensure_not_symlink_escape(spec.state_dir, spec.project_root, label="service state directory")
    spec.state_dir.mkdir(parents=True, exist_ok=True)
    ensure_not_symlink_escape(spec.state_dir, spec.project_root, label="service state directory")
    payload = {
        "version": SERVICE_VERSION,
        "kind": kind,
        "label": spec.label,
        "project_root": str(spec.project_root),
        "interval_seconds": spec.interval_seconds,
        "path": str(Path(path).expanduser()),
        "command": [
            spec.python_executable,
            "-m",
            "skillloop.cli",
            "--path",
            str(spec.project_root),
            "controller",
            "run",
        ],
        "python_path": spec.python_path,
    }
    spec.metadata_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return spec.metadata_path


def read_service_metadata(state_dir: str | Path) -> dict[str, Any] | None:
    path = Path(state_dir).expanduser().resolve() / "service.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def supported_default_kind() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "launchd"
    if system == "linux":
        return "systemd"
    return "unsupported"


# Backward-compatible facade over the launchd implementation. The launchd
# logic now lives behind the ServiceManager port in
# skillloop.infrastructure.services.launchd; these names resolve to it so
# existing callers (cli.py, tests) are unaffected.
from skillloop.infrastructure.services.launchd import (  # noqa: E402
    LaunchdServiceManager,
    default_launch_agents_dir,
    launchd_plist,
    launchd_plist_path,
    remove_launchd_service,
    write_launchd_service,
)
from skillloop.infrastructure.services import (  # noqa: E402
    available_kinds,
    get_service_manager,
)
from skillloop.ports.service_manager import ServiceManager, ServiceState  # noqa: E402

__all__ = [
    "SERVICE_VERSION",
    "DEFAULT_INTERVAL_SECONDS",
    "ServiceSpec",
    "ServiceManager",
    "ServiceState",
    "default_label",
    "validate_launchd_label",
    "build_service_spec",
    "write_service_metadata",
    "read_service_metadata",
    "supported_default_kind",
    "launchd_plist",
    "default_launch_agents_dir",
    "launchd_plist_path",
    "write_launchd_service",
    "remove_launchd_service",
    "available_kinds",
    "get_service_manager",
    "LaunchdServiceManager",
]
