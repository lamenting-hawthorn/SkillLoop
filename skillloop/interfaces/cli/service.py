from __future__ import annotations

import argparse
import json

from skillloop.application.requests import ServiceInstallRequest
from skillloop.application.service import ServiceService
from skillloop.interfaces.cli._shared import _service_interval_seconds, _store
from skillloop.service import get_service_manager, supported_default_kind


def cmd_service_install(args: argparse.Namespace) -> int:
    store = _store(args)
    req = ServiceInstallRequest(
        kind=args.kind,
        interval_seconds=_service_interval_seconds(args),
        label=args.label,
        launch_agents_dir=args.launch_agents_dir,
    )
    path, spec = ServiceService(store).install(req)
    kind = args.kind or supported_default_kind()
    manager = get_service_manager(kind)
    for line in manager.install_message(spec, path):
        print(line)
    return 0


def cmd_service_status(args: argparse.Namespace) -> int:
    store = _store(args)
    metadata = ServiceService(store).status()
    if args.json:
        print(json.dumps(metadata or {"installed": False}, indent=2, ensure_ascii=False))
        return 0
    if not metadata:
        print("SkillLoop service: not installed")
        return 0
    manager = get_service_manager(metadata["kind"])
    for line in manager.status_message(metadata):
        print(line)
    return 0


def cmd_service_uninstall(args: argparse.Namespace) -> int:
    store = _store(args)
    removed = ServiceService(store).uninstall(args.launch_agents_dir)
    if not removed:
        print("No SkillLoop service files found.")
        return 0
    for path in removed:
        print(f"removed {path}")
    return 0


__all__ = ["cmd_service_install", "cmd_service_status", "cmd_service_uninstall"]
