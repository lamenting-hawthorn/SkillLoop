from __future__ import annotations

import argparse
from pathlib import Path

from skillloop.application.controller import ControllerService
from skillloop.application.requests import SetupRequest
from skillloop.interfaces.cli._shared import _store


def cmd_setup(args: argparse.Namespace) -> int:
    store = _store(args)
    store.init()
    req = SetupRequest(
        connect=args.connect,
        db_path=Path(args.db_path).expanduser().resolve(),
        max_sessions=args.max_sessions,
        min_score=args.min_score,
        auto_export=args.auto_export,
        dataset_out=args.dataset_out,
        start=args.start,
    )
    result = ControllerService(store).setup(req)
    print(f"Wrote policy to {result.policy_path}")
    if result.report is not None:
        print(f"Ran controller tick {result.report.id}: {result.report.summary}")
    return 0


__all__ = ["cmd_setup"]
