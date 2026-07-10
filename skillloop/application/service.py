from __future__ import annotations

from pathlib import Path

from skillloop.service import (
    build_service_spec,
    read_service_metadata,
    remove_launchd_service,
    supported_default_kind,
    write_launchd_service,
)
from skillloop.store import SkillLoopStore

from .requests import ServiceInstallRequest


class ServiceService:
    def __init__(self, store: SkillLoopStore) -> None:
        self._store = store

    def install(self, req: ServiceInstallRequest) -> tuple[str, object]:
        self._store.init()
        kind = req.kind or supported_default_kind()
        if kind != "launchd":
            raise SystemExit(
                f"Unsupported service kind for install: {kind}. Currently implemented: launchd"
            )
        spec = build_service_spec(
            project_root=self._store.root,
            state_dir=self._store.state_dir,
            interval_seconds=req.interval_seconds,
            label=req.label,
        )
        return str(write_launchd_service(spec, launch_agents_dir=req.launch_agents_dir)), spec

    def status(self) -> dict | None:
        return read_service_metadata(self._store.state_dir)

    def uninstall(self, launch_agents_dir: str | None) -> list[Path]:
        return remove_launchd_service(
            state_dir=self._store.state_dir, launch_agents_dir=launch_agents_dir
        )


__all__ = ["ServiceService"]
