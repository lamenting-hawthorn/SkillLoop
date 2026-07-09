from __future__ import annotations

import argparse
from pathlib import Path

from skillloop.application.export import ExportService
from skillloop.application.requests import ExportRequest
from skillloop.interfaces.cli._shared import _resolve_trace, _store


def cmd_export(args: argparse.Namespace) -> int:
    store = _store(args)
    traces = store.list_traces()
    if args.trace_id:
        traces = [_resolve_trace(store, args.trace_id)]
    req = ExportRequest(
        format=args.format,
        out=Path(args.out),
        manifest_out=Path(args.manifest_out) if args.manifest_out else None,
        splits=args.splits,
        trace_id=args.trace_id,
        min_score=args.min_score,
    )
    result = ExportService(store).export(traces, req)
    if result.okf_bundle is not None:
        print(f"Exported OKF bundle to {result.okf_bundle}")
        return 0
    print(
        f"Exported {result.records} {result.format.upper()} record(s) to "
        f"{', '.join(str(path) for path in result.output_files.values())}"
    )
    print(f"Wrote manifest to {result.manifest_path}")
    return 0


__all__ = ["cmd_export"]
