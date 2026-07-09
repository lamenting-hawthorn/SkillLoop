from __future__ import annotations

import argparse

from skillloop.application.distill import DistillService
from skillloop.interfaces.cli._shared import _resolve_trace, _store


def cmd_distill(args: argparse.Namespace) -> int:
    store = _store(args)
    trace = _resolve_trace(store, args.trace_id)
    source_evaluation = store.latest_evaluation(trace.id)
    result = DistillService(store).distill(trace, source_evaluation)
    print(f"Created {len(result.created)} proposal(s); skipped {len(result.duplicates)} duplicate(s)")
    for entry in result.entries:
        marker = "new" if entry.is_new else "duplicate"
        print(f"{entry.saved_id[:12]}\t{marker}\t{entry.proposal.kind}\t{entry.proposal.title}")
    return 0


__all__ = ["cmd_distill"]
