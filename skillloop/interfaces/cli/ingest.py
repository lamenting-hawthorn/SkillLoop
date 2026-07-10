from __future__ import annotations

import argparse
import json
from pathlib import Path

from skillloop.application.ingest import IngestionService
from skillloop.application.requests import IngestionRequest
from skillloop.interfaces.cli._shared import _resolve_trace, _store


def cmd_ingest(args: argparse.Namespace) -> int:
    store = _store(args)
    req = IngestionRequest(
        adapter=args.adapter,
        input=Path(args.input) if args.input else None,
        db_path=Path(args.db_path).expanduser().resolve(),
        session_id=args.session_id,
        latest=args.latest,
    )
    trace, trace_id = IngestionService(store).ingest(req)
    print(f"Ingested {trace.source} trace {trace_id} ({len(trace.messages)} messages)")
    return 0


def cmd_traces_list(args: argparse.Namespace) -> int:
    store = _store(args)
    traces = store.list_traces()
    if not traces:
        print("No traces found.")
        return 0
    for trace in traces:
        print(
            f"{trace.id[:12]}\t{trace.source}\t{trace.created_at}\t{len(trace.messages)} messages"
        )
    return 0


def cmd_traces_show(args: argparse.Namespace) -> int:
    store = _store(args)
    trace = _resolve_trace(store, args.trace_id)
    print(json.dumps(trace.to_dict(), indent=2, ensure_ascii=False))
    return 0


__all__ = ["cmd_ingest", "cmd_traces_list", "cmd_traces_show"]
