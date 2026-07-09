from __future__ import annotations

import argparse
import json

from skillloop.application.controller import ControllerService
from skillloop.interfaces.cli._shared import _store


def cmd_controller_run(args: argparse.Namespace) -> int:
    store = _store(args)
    report = ControllerService(store).run()
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_controller_history(args: argparse.Namespace) -> int:
    store = _store(args)
    if args.limit is not None and args.limit <= 0:
        raise SystemExit("--limit must be positive")
    runs = ControllerService(store).history(args.limit)
    if not runs:
        print("No controller runs found.")
        return 0
    for run in runs:
        summary = run.get("summary", {})
        print(
            f"{run.get('id')}\t{run.get('finished_at') or run.get('started_at')}\t"
            f"errors={summary.get('errors', 0)}\t"
            f"traces={summary.get('traces_seen', 0)}\t"
            f"evaluated={summary.get('traces_evaluated', 0)}\t"
            f"review={summary.get('requires_review', 0)}"
        )
    return 0


def cmd_controller_show(args: argparse.Namespace) -> int:
    store = _store(args)
    run = ControllerService(store).show(args.run_id)
    print(json.dumps(run, indent=2, ensure_ascii=False))
    return 0


__all__ = ["cmd_controller_run", "cmd_controller_history", "cmd_controller_show"]
