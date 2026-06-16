from __future__ import annotations

import hashlib
import json
import platform
import plistlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
    return ServiceSpec(
        label=label or default_label(root),
        project_root=root,
        state_dir=state,
        interval_seconds=interval_seconds,
        python_executable=python_executable or sys.executable,
        python_path=str(Path(__file__).resolve().parents[1]),
    )


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


def default_launch_agents_dir() -> Path:
    return Path.home() / "Library" / "LaunchAgents"


def launchd_plist_path(spec: ServiceSpec, launch_agents_dir: str | Path | None = None) -> Path:
    base = Path(launch_agents_dir).expanduser() if launch_agents_dir else default_launch_agents_dir()
    return base / f"{spec.label}.plist"


def write_launchd_service(spec: ServiceSpec, *, launch_agents_dir: str | Path | None = None) -> Path:
    spec.state_dir.mkdir(parents=True, exist_ok=True)
    plist_path = launchd_plist_path(spec, launch_agents_dir)
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    with plist_path.open("wb") as fh:
        plistlib.dump(launchd_plist(spec), fh, sort_keys=False)
    write_service_metadata(spec, kind="launchd", path=plist_path)
    return plist_path


def write_service_metadata(spec: ServiceSpec, *, kind: str, path: str | Path) -> Path:
    spec.state_dir.mkdir(parents=True, exist_ok=True)
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


def remove_launchd_service(*, state_dir: str | Path, launch_agents_dir: str | Path | None = None) -> list[Path]:
    state = Path(state_dir).expanduser().resolve()
    metadata = read_service_metadata(state)
    removed: list[Path] = []
    candidate_paths: list[Path] = []
    if metadata and metadata.get("path"):
        candidate_paths.append(Path(str(metadata["path"])).expanduser())
    if metadata and metadata.get("label"):
        candidate_paths.append(launchd_plist_path(
            build_service_spec(
                project_root=metadata.get("project_root") or Path.cwd(),
                state_dir=state,
                label=str(metadata["label"]),
                interval_seconds=int(metadata.get("interval_seconds") or DEFAULT_INTERVAL_SECONDS),
            ),
            launch_agents_dir,
        ))
    for path in dict.fromkeys(candidate_paths):
        if path.exists():
            path.unlink()
            removed.append(path)
    metadata_path = state / "service.json"
    if metadata_path.exists():
        metadata_path.unlink()
        removed.append(metadata_path)
    return removed


def supported_default_kind() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "launchd"
    if system == "linux":
        return "systemd"
    return "unsupported"
