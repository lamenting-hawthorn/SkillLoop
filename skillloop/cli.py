from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from skillloop.adapters.generic_jsonl import load_generic_jsonl
from skillloop.adapters.hermes import load_hermes_export, load_hermes_state_db
from skillloop.apply.filesystem import export_approved
from skillloop.benchmark import replay_benchmark, write_benchmark_report
from skillloop.dataset import build_manifest, parse_split_spec, split_records, write_jsonl, write_manifest
from skillloop.distill.memory import propose_memory_updates
from skillloop.distill.skills import propose_skill_updates
from skillloop.eval.registry import default_evaluator_registry
from skillloop.export.dpo import export_dpo_records
from skillloop.export.sft import export_sft_records
from skillloop.conditions import LoopCondition
from skillloop.loop import LoopSchedule, load_schedule, proposals_with_provenance, run_outer_loop, save_schedule, tick
from skillloop.schema import AgentTrace, Evaluation, Proposal
from skillloop.store import SkillLoopStore
from skillloop.training_config import TrainingConfigRequest, generate_training_config


def _store(args: argparse.Namespace) -> SkillLoopStore:
    return SkillLoopStore(Path(args.path))


def _resolve_trace(store: SkillLoopStore, trace_ref: str) -> AgentTrace:
    traces = store.list_traces()
    if trace_ref == "latest":
        if not traces:
            raise SystemExit("No traces found. Run `skillloop ingest ...` first.")
        return traces[0]
    matches = [trace for trace in traces if trace.id == trace_ref or trace.id.startswith(trace_ref)]
    if not matches:
        raise SystemExit(f"Trace not found: {trace_ref}")
    if len(matches) > 1:
        raise SystemExit(f"Trace id prefix is ambiguous: {trace_ref}")
    return matches[0]


def _write_jsonl(path: str | Path, records: list[dict]) -> Path:
    out = Path(path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + ("\n" if records else ""), encoding="utf-8")
    return out


def cmd_init(args: argparse.Namespace) -> int:
    store = _store(args)
    store.init()
    print(f"Initialized SkillLoop at {store.state_dir}")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    store = _store(args)
    if args.adapter == "generic":
        if not args.input:
            raise SystemExit("generic ingest requires an input JSONL path")
        trace = load_generic_jsonl(args.input)
    elif args.adapter == "hermes":
        if not args.input:
            raise SystemExit("hermes ingest requires an input JSON path")
        trace = load_hermes_export(args.input)
    elif args.adapter == "hermes-db":
        trace = load_hermes_state_db(args.db_path, session_id=args.session_id, latest=args.latest)
    else:
        raise SystemExit(f"Unsupported adapter: {args.adapter}")
    trace_id = store.save_trace(trace)
    print(f"Ingested {trace.source} trace {trace_id} ({len(trace.messages)} messages)")
    return 0


def cmd_traces_list(args: argparse.Namespace) -> int:
    store = _store(args)
    traces = store.list_traces()
    if not traces:
        print("No traces found.")
        return 0
    for trace in traces:
        print(f"{trace.id[:12]}\t{trace.source}\t{trace.created_at}\t{len(trace.messages)} messages")
    return 0


def cmd_traces_show(args: argparse.Namespace) -> int:
    store = _store(args)
    trace = _resolve_trace(store, args.trace_id)
    print(json.dumps(trace.to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    store = _store(args)
    trace = _resolve_trace(store, args.trace_id)
    registry = default_evaluator_registry()
    evaluation = registry.evaluate(trace, name=args.evaluator)
    store.save_evaluation(evaluation)
    print(json.dumps(evaluation.to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_distill(args: argparse.Namespace) -> int:
    store = _store(args)
    trace = _resolve_trace(store, args.trace_id)
    source_evaluation = store.latest_evaluation(trace.id)
    proposals = proposals_with_provenance(trace.id, propose_memory_updates(trace) + propose_skill_updates(trace), source_evaluation)
    saved: list[tuple[Proposal, str, bool]] = []
    for proposal in proposals:
        saved_id = store.save_proposal(proposal)
        saved.append((proposal, saved_id, saved_id == proposal.id))
    created = [proposal for proposal, _, is_new in saved if is_new]
    duplicates = [saved_id for _, saved_id, is_new in saved if not is_new]
    print(f"Created {len(created)} proposal(s); skipped {len(duplicates)} duplicate(s)")
    for proposal, saved_id, is_new in saved:
        marker = "new" if is_new else "duplicate"
        print(f"{saved_id[:12]}\t{marker}\t{proposal.kind}\t{proposal.title}")
    return 0


def cmd_review_list(args: argparse.Namespace) -> int:
    store = _store(args)
    proposals = store.list_proposals(status=None if args.all else args.status)
    if not proposals:
        print("No proposals found.")
        return 0
    for proposal in proposals:
        print(f"{proposal.id[:12]}\t{proposal.status}\t{proposal.kind}\t{proposal.title}")
        if args.verbose:
            print(f"  reason: {proposal.reason}")
            print(f"  content: {proposal.content[:240].replace(chr(10), ' ')}")
    return 0


def _resolve_proposal(store: SkillLoopStore, proposal_ref: str):
    proposals = store.list_proposals(status=None)
    matches = [proposal for proposal in proposals if proposal.id == proposal_ref or proposal.id.startswith(proposal_ref)]
    if not matches:
        raise SystemExit(f"Proposal not found: {proposal_ref}")
    if len(matches) > 1:
        raise SystemExit(f"Proposal id prefix is ambiguous: {proposal_ref}")
    return matches[0]


def cmd_review_approve(args: argparse.Namespace) -> int:
    store = _store(args)
    proposal = _resolve_proposal(store, args.proposal_id)
    proposal.status = "approved"
    store.save_proposal(proposal)
    print(f"Approved {proposal.id}")
    return 0


def cmd_review_reject(args: argparse.Namespace) -> int:
    store = _store(args)
    proposal = _resolve_proposal(store, args.proposal_id)
    proposal.status = "rejected"
    store.save_proposal(proposal)
    print(f"Rejected {proposal.id}")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    store = _store(args)
    written = export_approved(store, out_dir=args.out_dir)
    if not written:
        print("No approved proposals to export.")
        return 0
    for path in written:
        print(path)
    return 0


def _evaluations_by_trace(store: SkillLoopStore, traces: list[AgentTrace]) -> dict[str, Evaluation]:
    result: dict[str, Evaluation] = {}
    for trace in traces:
        latest = store.latest_evaluation(trace.id)
        if latest is not None:
            result[trace.id] = latest
    return result


def _proposals_by_trace(store: SkillLoopStore, traces: list[AgentTrace]) -> dict[str, list[Proposal]]:
    wanted = {trace.id for trace in traces}
    result = {trace.id: [] for trace in traces}
    for proposal in store.list_proposals(status=None):
        if proposal.trace_id in wanted:
            result[proposal.trace_id].append(proposal)
    return result


def cmd_export(args: argparse.Namespace) -> int:
    store = _store(args)
    traces = store.list_traces()
    if args.trace_id:
        traces = [_resolve_trace(store, args.trace_id)]
    if args.min_score is not None:
        filtered = []
        for trace in traces:
            evaluations = store.list_evaluations(trace.id)
            best_score = max((evaluation.score for evaluation in evaluations), default=None)
            if best_score is not None and best_score >= args.min_score:
                filtered.append(trace)
        traces = filtered
    evaluations_by_trace = _evaluations_by_trace(store, traces)
    proposals_by_trace = _proposals_by_trace(store, traces)
    if args.format == "sft":
        records = export_sft_records(traces, evaluations_by_trace=evaluations_by_trace, proposals_by_trace=proposals_by_trace)
    elif args.format == "dpo":
        records = export_dpo_records(traces, evaluations_by_trace=evaluations_by_trace, proposals_by_trace=proposals_by_trace)
    else:
        raise SystemExit(f"Unsupported export format: {args.format}")

    split_spec = parse_split_spec(args.splits)
    split_map = split_records(records, split_spec)
    output_files: dict[str, Path] = {}
    out = Path(args.out).resolve()
    if len(split_map) == 1 and "train" in split_map:
        output_files["train"] = write_jsonl(out, split_map["train"])
    else:
        for split_name, split_items in split_map.items():
            split_path = out.with_name(f"{out.stem}.{split_name}{out.suffix or '.jsonl'}")
            output_files[split_name] = write_jsonl(split_path, split_items)

    manifest = build_manifest(
        kind=args.format,
        split_outputs=output_files,
        split_records_map=split_map,
        source_traces=traces,
        evaluations_by_trace=evaluations_by_trace,
        proposals_by_trace=proposals_by_trace,
        export_metadata={"min_score": args.min_score, "split_spec": args.splits or "train=1.0"},
    )
    manifest_path = Path(args.manifest_out).resolve() if args.manifest_out else out.with_suffix(out.suffix + ".manifest.json")
    write_manifest(manifest_path, manifest)
    print(f"Exported {len(records)} {args.format.upper()} record(s) to {', '.join(str(path) for path in output_files.values())}")
    print(f"Wrote manifest to {manifest_path}")
    return 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    store = _store(args)
    traces = store.list_traces()
    if args.trace_id:
        traces = [_resolve_trace(store, args.trace_id)]
    registry = default_evaluator_registry()
    candidates = [item.strip() for item in args.candidates.split(",") if item.strip()]
    report = replay_benchmark(traces, registry, baseline=args.baseline, candidates=candidates)
    if args.out:
        out = write_benchmark_report(args.out, report)
        print(f"Wrote benchmark report to {out}")
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_training_config(args: argparse.Namespace) -> int:
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
    summary = generate_training_config(request)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def _condition_from_args(args: argparse.Namespace) -> LoopCondition:
    if getattr(args, "condition", None):
        condition = LoopCondition.from_json(args.condition)
        if not getattr(args, "min_score_explicit", False):
            return condition
        return LoopCondition(
            score_gte=args.min_score,
            required_tags=condition.required_tags,
            forbidden_tags=condition.forbidden_tags,
            max_iterations=condition.max_iterations,
        )
    return LoopCondition(
        score_gte=args.min_score,
        required_tags=tuple(getattr(args, "require_tag", []) or []),
        forbidden_tags=tuple(getattr(args, "forbid_tag", []) or []),
        max_iterations=getattr(args, "max_iterations", None),
    )


def cmd_loop_run(args: argparse.Namespace) -> int:
    store = _store(args)
    condition = _condition_from_args(args)
    summary = run_outer_loop(
        store,
        evaluator=args.evaluator,
        min_score=args.min_score,
        condition=condition,
        only_unevaluated=not args.all,
        distill_failures=not args.no_distill_failures,
        limit=args.limit,
    )
    print(json.dumps(summary.to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_loop_schedule(args: argparse.Namespace) -> int:
    store = _store(args)
    condition = _condition_from_args(args)
    schedule = LoopSchedule(
        interval=args.interval,
        evaluator=args.evaluator,
        min_score=condition.score_gte,
        condition=condition,
        only_unevaluated=not args.all,
        distill_failures=not args.no_distill_failures,
        limit=args.limit,
    )
    path = save_schedule(store, schedule)
    print(f"Wrote loop schedule to {path}")
    print(json.dumps(schedule.to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_loop_status(args: argparse.Namespace) -> int:
    store = _store(args)
    try:
        schedule = load_schedule(store)
    except FileNotFoundError:
        print("No loop schedule configured. Run `skillloop loop schedule ...` first.")
        return 0
    print(json.dumps(schedule.to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_loop_tick(args: argparse.Namespace) -> int:
    store = _store(args)
    ran, summary, schedule = tick(store, force=args.force)
    payload = {"ran": ran, "schedule": schedule.to_dict(), "summary": summary.to_dict() if summary is not None else None}
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SkillLoop: clean learning/export layer for agent traces")
    parser.add_argument("--path", default=".", help="Project root for .skillloop state (default: current directory)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Initialize local .skillloop state")
    p_init.set_defaults(func=cmd_init)

    p_ingest = sub.add_parser("ingest", help="Ingest a trace")
    p_ingest.add_argument("adapter", choices=["generic", "hermes", "hermes-db"])
    p_ingest.add_argument("input", nargs="?", help="Input JSONL/JSON path for generic or hermes adapters")
    p_ingest.add_argument("--db-path", default=str(Path.home() / ".hermes" / "state.db"), help="Hermes state.db path for hermes-db adapter")
    p_ingest.add_argument("--session-id", default=None, help="Hermes session id for hermes-db adapter")
    p_ingest.add_argument("--latest", action="store_true", help="Use latest Hermes session with messages for hermes-db adapter")
    p_ingest.set_defaults(func=cmd_ingest)

    p_traces = sub.add_parser("traces", help="List/show traces")
    traces_sub = p_traces.add_subparsers(dest="traces_command", required=True)
    p_traces_list = traces_sub.add_parser("list")
    p_traces_list.set_defaults(func=cmd_traces_list)
    p_traces_show = traces_sub.add_parser("show")
    p_traces_show.add_argument("trace_id")
    p_traces_show.set_defaults(func=cmd_traces_show)

    p_eval = sub.add_parser("eval", help="Evaluate a trace")
    p_eval.add_argument("trace_id", help="Trace id/prefix, or latest")
    p_eval.add_argument("--evaluator", default="rubric", help="Registered evaluator name (default: rubric)")
    p_eval.set_defaults(func=cmd_eval)

    p_distill = sub.add_parser("distill", help="Create memory/skill proposals from a trace")
    p_distill.add_argument("trace_id", help="Trace id/prefix, or latest")
    p_distill.set_defaults(func=cmd_distill)

    p_review = sub.add_parser("review", help="Review proposals")
    review_sub = p_review.add_subparsers(dest="review_command", required=True)
    p_review_list = review_sub.add_parser("list")
    p_review_list.add_argument("--status", default="pending", choices=["pending", "approved", "rejected"])
    p_review_list.add_argument("--all", action="store_true")
    p_review_list.add_argument("--verbose", "-v", action="store_true")
    p_review_list.set_defaults(func=cmd_review_list)
    p_review_approve = review_sub.add_parser("approve")
    p_review_approve.add_argument("proposal_id")
    p_review_approve.set_defaults(func=cmd_review_approve)
    p_review_reject = review_sub.add_parser("reject")
    p_review_reject.add_argument("proposal_id")
    p_review_reject.set_defaults(func=cmd_review_reject)

    p_apply = sub.add_parser("apply", help="Cleanly export approved proposals under .skillloop/approved")
    p_apply.add_argument("--out-dir", default=None)
    p_apply.set_defaults(func=cmd_apply)

    p_export = sub.add_parser("export", help="Export fine-tuning-ready JSONL")
    p_export.add_argument("format", choices=["sft", "dpo"])
    p_export.add_argument("--out", required=True)
    p_export.add_argument("--manifest-out", default=None, help="Optional manifest JSON path (default: <out>.manifest.json)")
    p_export.add_argument("--splits", default=None, help="Optional split ratios, e.g. train=0.8,validation=0.1,test=0.1")
    p_export.add_argument("--trace-id", default=None, help="Optional trace id/prefix, or latest")
    p_export.add_argument("--min-score", type=int, default=None, help="Only export traces with an evaluation score >= this value")
    p_export.set_defaults(func=cmd_export)

    p_benchmark = sub.add_parser("benchmark", help="Replay traces through evaluator versions and compare scores")
    p_benchmark.add_argument("--baseline", default="rubric_legacy", help="Baseline evaluator name (default: rubric_legacy)")
    p_benchmark.add_argument("--candidates", default="rubric", help="Comma-separated candidate evaluator names (default: rubric)")
    p_benchmark.add_argument("--trace-id", default=None, help="Optional trace id/prefix, or latest")
    p_benchmark.add_argument("--out", default=None, help="Optional JSON report path")
    p_benchmark.set_defaults(func=cmd_benchmark)

    p_training = sub.add_parser("training-config", help="Generate training configs only; does not run training")
    p_training.add_argument("target", choices=["unsloth", "trl", "axolotl"])
    p_training.add_argument("--dataset-manifest", required=True)
    p_training.add_argument("--base-model", required=True)
    p_training.add_argument("--output-dir", required=True)
    p_training.add_argument("--config-dir", required=True)
    p_training.add_argument("--learning-rate", type=float, default=2e-4)
    p_training.add_argument("--epochs", type=int, default=1)
    p_training.add_argument("--per-device-batch-size", type=int, default=1)
    p_training.add_argument("--gradient-accumulation-steps", type=int, default=4)
    p_training.add_argument("--max-seq-length", type=int, default=2048)
    p_training.add_argument("--lora-rank", type=int, default=16)
    p_training.add_argument("--lora-alpha", type=int, default=16)
    p_training.set_defaults(func=cmd_training_config)

    p_loop = sub.add_parser("loop", help="Run and schedule the outer self-improvement loop")
    loop_sub = p_loop.add_subparsers(dest="loop_command", required=True)

    p_loop_run = loop_sub.add_parser("run", help="Run one outer-loop evaluation/distillation pass now")
    p_loop_run.add_argument("--evaluator", default="rubric")
    p_loop_run.add_argument("--min-score", type=int, default=70)
    p_loop_run.add_argument("--condition", default=None, help="JSON loop condition, e.g. '{\"score_gte\":80,\"forbidden_tags\":[\"tool_failure\"]}'")
    p_loop_run.add_argument("--require-tag", action="append", default=[], help="Require evaluation tag for done condition; repeatable")
    p_loop_run.add_argument("--forbid-tag", action="append", default=[], help="Fail done condition if evaluation tag is present; repeatable")
    p_loop_run.add_argument("--max-iterations", type=int, default=None, help="Stop continuing a trace after this many prior evaluations")
    p_loop_run.add_argument("--all", action="store_true", help="Re-evaluate traces that already have evaluations")
    p_loop_run.add_argument("--no-distill-failures", action="store_true", help="Do not create proposals for traces below min-score")
    p_loop_run.add_argument("--limit", type=int, default=None)
    p_loop_run.set_defaults(func=cmd_loop_run)

    p_loop_schedule = loop_sub.add_parser("schedule", help="Write a project-local loop schedule")
    p_loop_schedule.add_argument("--interval", choices=["hourly", "daily", "weekly"], default="daily")
    p_loop_schedule.add_argument("--evaluator", default="rubric")
    p_loop_schedule.add_argument("--min-score", type=int, default=70)
    p_loop_schedule.add_argument("--condition", default=None, help="JSON loop condition persisted into the schedule")
    p_loop_schedule.add_argument("--require-tag", action="append", default=[])
    p_loop_schedule.add_argument("--forbid-tag", action="append", default=[])
    p_loop_schedule.add_argument("--max-iterations", type=int, default=None)
    p_loop_schedule.add_argument("--all", action="store_true", help="Re-evaluate traces that already have evaluations")
    p_loop_schedule.add_argument("--no-distill-failures", action="store_true")
    p_loop_schedule.add_argument("--limit", type=int, default=None)
    p_loop_schedule.set_defaults(func=cmd_loop_schedule)

    p_loop_status = loop_sub.add_parser("status", help="Show current project-local loop schedule")
    p_loop_status.set_defaults(func=cmd_loop_status)

    p_loop_tick = loop_sub.add_parser("tick", help="Run scheduled loop if due, updating last/next run times")
    p_loop_tick.add_argument("--force", action="store_true", help="Run even if the schedule is not due")
    p_loop_tick.set_defaults(func=cmd_loop_tick)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except BrokenPipeError:
        return 1


if __name__ == "__main__":
    sys.exit(main())
