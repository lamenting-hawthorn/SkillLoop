from __future__ import annotations

import argparse
import json

from skillloop.application.loop import LoopService
from skillloop.application.requests import LoopRunRequest, LoopScheduleRequest
from skillloop.interfaces.cli._shared import _condition_from_args, _store


def cmd_loop_run(args: argparse.Namespace) -> int:
    store = _store(args)
    condition = _condition_from_args(args)
    req = LoopRunRequest(
        evaluator=args.evaluator,
        min_score=args.min_score,
        condition=condition,
        require_tag=tuple(getattr(args, "require_tag", []) or []),
        forbid_tag=tuple(getattr(args, "forbid_tag", []) or []),
        max_iterations=getattr(args, "max_iterations", None),
        reevaluate_all=args.all,
        distill_failures=not args.no_distill_failures,
        limit=args.limit,
    )
    summary = LoopService().run(store, req)
    print(json.dumps(summary.to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_loop_schedule(args: argparse.Namespace) -> int:
    store = _store(args)
    condition = _condition_from_args(args)
    req = LoopScheduleRequest(
        interval=args.interval,
        evaluator=args.evaluator,
        min_score=args.min_score,
        condition=condition,
        require_tag=tuple(getattr(args, "require_tag", []) or []),
        forbid_tag=tuple(getattr(args, "forbid_tag", []) or []),
        max_iterations=getattr(args, "max_iterations", None),
        reevaluate_all=args.all,
        distill_failures=not args.no_distill_failures,
        limit=args.limit,
    )
    path = LoopService().schedule(store, req)
    print(f"Wrote loop schedule to {path}")
    print(json.dumps(LoopService().status(store).to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_loop_status(args: argparse.Namespace) -> int:
    store = _store(args)
    try:
        schedule = LoopService().status(store)
    except FileNotFoundError:
        print("No loop schedule configured. Run `skillloop loop schedule ...` first.")
        return 0
    print(json.dumps(schedule.to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_loop_tick(args: argparse.Namespace) -> int:
    store = _store(args)
    result = LoopService().tick(store, force=args.force)
    payload = {
        "ran": result.ran,
        "schedule": result.schedule.to_dict(),
        "summary": result.summary.to_dict() if result.summary is not None else None,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


__all__ = ["cmd_loop_run", "cmd_loop_schedule", "cmd_loop_status", "cmd_loop_tick"]
