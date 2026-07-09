from __future__ import annotations

import argparse
import json

from skillloop.application.requests import ServiceInstallRequest
from skillloop.application.service import ServiceService
from skillloop.interfaces.cli._shared import _service_interval_seconds, _store


def cmd_service_install(args: argparse.Namespace) -> int:
    store = _store(args)
    req = ServiceInstallRequest(
        kind=args.kind,
        interval_seconds=_service_interval_seconds(args),
        label=args.label,
        launch_agents_dir=args.launch_agents_dir,
    )
    path, spec = ServiceService(store).install(req)
    print(f"Wrote launchd service plist to {path}")
    print(f"label: {spec.label}")
    print(f"interval_seconds: {spec.interval_seconds}")
    print("To start it now, run:")
    print(f"launchctl bootstrap gui/$(id -u) {path}")
    print("To stop it later, run:")
    print(f"launchctl bootout gui/$(id -u) {path}")
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
    from pathlib import Path

    path = Path(str(metadata.get("path", ""))).expanduser()
    print("SkillLoop service: installed")
    print(f"kind: {metadata.get('kind')}")
    print(f"label: {metadata.get('label')}")
    print(f"path: {path}")
    print(f"plist_exists: {path.exists()}")
    print(f"interval_seconds: {metadata.get('interval_seconds')}")
    print(f"command: {' '.join(str(part) for part in metadata.get('command', []))}")
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
