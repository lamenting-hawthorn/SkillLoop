from __future__ import annotations

import argparse

from skillloop.application.benchmark import BenchmarkService
from skillloop.application.requests import BenchmarkRequest
from skillloop.application.training import TrainingService
from skillloop.interfaces.cli._shared import _resolve_trace, _store
from skillloop.training_config import TrainingConfigRequest


def cmd_benchmark(args: argparse.Namespace) -> int:
    import json

    store = _store(args)
    traces = store.list_traces()
    if args.trace_id:
        traces = [_resolve_trace(store, args.trace_id)]
    candidates = [item.strip() for item in args.candidates.split(",") if item.strip()]
    req = BenchmarkRequest(baseline=args.baseline, candidates=candidates, trace_id=args.trace_id, out=args.out)
    report, out_path = BenchmarkService(store).run(traces, req)
    if out_path:
        print(f"Wrote benchmark report to {out_path}")
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_training_config(args: argparse.Namespace) -> int:
    import json

    request = TrainingConfigRequest(
        target=args.target,
        dataset_manifest=args.dataset_manifest,
        base_model=args.base_model,
        output_dir=args.output_dir,
        config_dir=args.config_dir,
        learning_rate=args.learning_rate,
        epochs=args.epochs,
        per_device_batch_size=args.per_device_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        max_seq_length=args.max_seq_length,
        lora_rank=args.lora_rank,
        lora_alpha=args.lora_alpha,
    )
    summary = TrainingService().generate(request)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


__all__ = ["cmd_benchmark", "cmd_training_config"]
