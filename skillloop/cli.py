from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from skillloop.adapters.generic_jsonl import load_generic_jsonl
from skillloop.adapters.hermes import load_hermes_export, load_hermes_state_db
from skillloop.apply.filesystem import export_approved
from skillloop.distill.memory import propose_memory_updates
from skillloop.distill.skills import propose_skill_updates
from skillloop.eval.rubric import evaluate_trace
from skillloop.export.dpo import export_dpo_records
from skillloop.export.sft import export_sft_records
from skillloop.schema import AgentTrace
from skillloop.store import SkillLoopStore


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
    evaluation = evaluate_trace(trace)
    store.save_evaluation(evaluation)
    print(json.dumps(evaluation.to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_distill(args: argparse.Namespace) -> int:
    store = _store(args)
    trace = _resolve_trace(store, args.trace_id)
    proposals = propose_memory_updates(trace) + propose_skill_updates(trace)
    for proposal in proposals:
        store.save_proposal(proposal)
    print(f"Created {len(proposals)} proposal(s)")
    for proposal in proposals:
        print(f"{proposal.id[:12]}\t{proposal.kind}\t{proposal.title}")
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
    if args.format == "sft":
        records = export_sft_records(traces)
    elif args.format == "dpo":
        records = export_dpo_records(traces)
    else:
        raise SystemExit(f"Unsupported export format: {args.format}")
    out = _write_jsonl(args.out, records)
    print(f"Exported {len(records)} {args.format.upper()} record(s) to {out}")
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
    p_export.add_argument("--trace-id", default=None, help="Optional trace id/prefix, or latest")
    p_export.add_argument("--min-score", type=int, default=None, help="Only export traces with an evaluation score >= this value")
    p_export.set_defaults(func=cmd_export)

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
