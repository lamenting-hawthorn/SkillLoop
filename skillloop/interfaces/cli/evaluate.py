from __future__ import annotations

import argparse
import json

from skillloop.application.evaluate import EvaluationService
from skillloop.interfaces.cli._shared import _resolve_trace, _store


def cmd_eval(args: argparse.Namespace) -> int:
    store = _store(args)
    trace = _resolve_trace(store, args.trace_id)
    evaluation = EvaluationService(store).evaluate(trace, evaluator=args.evaluator)
    print(json.dumps(evaluation.to_dict(), indent=2, ensure_ascii=False))
    return 0


__all__ = ["cmd_eval"]
