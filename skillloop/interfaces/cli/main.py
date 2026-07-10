from __future__ import annotations

import argparse
from pathlib import Path

from skillloop import __version__
from skillloop.interfaces.cli.controller import (
    cmd_controller_history,
    cmd_controller_run,
    cmd_controller_show,
)
from skillloop.interfaces.cli.dataset import cmd_benchmark, cmd_training_config
from skillloop.interfaces.cli.distill import cmd_distill
from skillloop.interfaces.cli.doctor import cmd_doctor
from skillloop.interfaces.cli.evaluate import cmd_eval
from skillloop.interfaces.cli.export import cmd_export
from skillloop.interfaces.cli.ingest import cmd_ingest, cmd_traces_list, cmd_traces_show
from skillloop.interfaces.cli.init import cmd_init
from skillloop.interfaces.cli.loop import (
    cmd_loop_run,
    cmd_loop_schedule,
    cmd_loop_status,
    cmd_loop_tick,
)
from skillloop.interfaces.cli.review import (
    cmd_apply,
    cmd_review_approve,
    cmd_review_list,
    cmd_review_reject,
)
from skillloop.interfaces.cli.service import (
    cmd_service_install,
    cmd_service_status,
    cmd_service_uninstall,
)
from skillloop.interfaces.cli.setup import cmd_setup
from skillloop.interfaces.cli.status import cmd_status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="SkillLoop: clean learning/export layer for agent traces"
    )
    parser.add_argument(
        "--path", default=".", help="Project root for .skillloop state (default: current directory)"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Initialize local .skillloop state")
    p_init.set_defaults(func=cmd_init)

    p_doctor = sub.add_parser(
        "doctor", help="Check installation, project state, policy, and connectors"
    )
    p_doctor.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    p_doctor.set_defaults(func=cmd_doctor)

    p_setup = sub.add_parser("setup", help="Configure SkillLoop as a local sidecar")
    p_setup.add_argument(
        "--connect",
        choices=["hermes"],
        required=True,
        help="Runtime to connect (currently: hermes)",
    )
    p_setup.add_argument(
        "--start",
        action="store_true",
        help="Run one controller tick immediately after writing policy",
    )
    p_setup.add_argument(
        "--db-path", default=str(Path.home() / ".hermes" / "state.db"), help="Hermes state.db path"
    )
    p_setup.add_argument(
        "--max-sessions", type=int, default=20, help="Maximum Hermes sessions to ingest per tick"
    )
    p_setup.add_argument("--min-score", type=int, default=70, help="Evaluation/dataset score gate")
    p_setup.add_argument(
        "--auto-export", action="store_true", help="Enable controller-managed SFT export"
    )
    p_setup.add_argument(
        "--dataset-out", default="data/sft.jsonl", help="Controller-managed SFT output path"
    )
    p_setup.set_defaults(func=cmd_setup)

    p_status = sub.add_parser("status", help="Show current SkillLoop state")
    p_status.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    p_status.set_defaults(func=cmd_status)

    p_ingest = sub.add_parser("ingest", help="Ingest a trace")
    p_ingest.add_argument("adapter", choices=["generic", "hermes", "hermes-db"])
    p_ingest.add_argument(
        "input", nargs="?", help="Input JSONL/JSON path for generic or hermes adapters"
    )
    p_ingest.add_argument(
        "--db-path",
        default=str(Path.home() / ".hermes" / "state.db"),
        help="Hermes state.db path for hermes-db adapter",
    )
    p_ingest.add_argument(
        "--session-id", default=None, help="Hermes session id for hermes-db adapter"
    )
    p_ingest.add_argument(
        "--latest",
        action="store_true",
        help="Use latest Hermes session with messages for hermes-db adapter",
    )
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
    p_eval.add_argument(
        "--evaluator", default="rubric", help="Registered evaluator name (default: rubric)"
    )
    p_eval.set_defaults(func=cmd_eval)

    p_distill = sub.add_parser("distill", help="Create memory/skill proposals from a trace")
    p_distill.add_argument("trace_id", help="Trace id/prefix, or latest")
    p_distill.set_defaults(func=cmd_distill)

    p_review = sub.add_parser("review", help="Review proposals")
    review_sub = p_review.add_subparsers(dest="review_command", required=True)
    p_review_list = review_sub.add_parser("list")
    p_review_list.add_argument(
        "--status", default="pending", choices=["pending", "approved", "rejected"]
    )
    p_review_list.add_argument("--all", action="store_true")
    p_review_list.add_argument("--verbose", "-v", action="store_true")
    p_review_list.set_defaults(func=cmd_review_list)
    p_review_approve = review_sub.add_parser("approve")
    p_review_approve.add_argument("proposal_id")
    p_review_approve.set_defaults(func=cmd_review_approve)
    p_review_reject = review_sub.add_parser("reject")
    p_review_reject.add_argument("proposal_id")
    p_review_reject.set_defaults(func=cmd_review_reject)

    p_apply = sub.add_parser(
        "apply", help="Cleanly export approved proposals under .skillloop/approved"
    )
    p_apply.add_argument("--out-dir", default=None)
    p_apply.set_defaults(func=cmd_apply)

    p_export = sub.add_parser("export", help="Export fine-tuning-ready JSONL")
    p_export.add_argument("format", choices=["sft", "dpo", "okf"])
    p_export.add_argument("--out", required=True)
    p_export.add_argument(
        "--manifest-out",
        default=None,
        help="Optional manifest JSON path (default: <out>.manifest.json)",
    )
    p_export.add_argument(
        "--splits",
        default=None,
        help="Optional split ratios, e.g. train=0.8,validation=0.1,test=0.1",
    )
    p_export.add_argument("--trace-id", default=None, help="Optional trace id/prefix, or latest")
    p_export.add_argument(
        "--min-score",
        type=int,
        default=None,
        help="Only export traces with an evaluation score >= this value",
    )
    p_export.set_defaults(func=cmd_export)

    p_benchmark = sub.add_parser(
        "benchmark", help="Replay traces through evaluator versions and compare scores"
    )
    p_benchmark.add_argument(
        "--baseline",
        default="rubric_legacy",
        help="Baseline evaluator name (default: rubric_legacy)",
    )
    p_benchmark.add_argument(
        "--candidates",
        default="rubric",
        help="Comma-separated candidate evaluator names (default: rubric)",
    )
    p_benchmark.add_argument("--trace-id", default=None, help="Optional trace id/prefix, or latest")
    p_benchmark.add_argument("--out", default=None, help="Optional JSON report path")
    p_benchmark.set_defaults(func=cmd_benchmark)

    p_training = sub.add_parser(
        "training-config", help="Generate training configs only; does not run training"
    )
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

    p_loop_run = loop_sub.add_parser(
        "run", help="Run one outer-loop evaluation/distillation pass now"
    )
    p_loop_run.add_argument("--evaluator", default="rubric")
    p_loop_run.add_argument("--min-score", type=int, default=70)
    p_loop_run.add_argument(
        "--condition",
        default=None,
        help='JSON loop condition, e.g. \'{"score_gte":80,"forbidden_tags":["tool_failure"]}\'',
    )
    p_loop_run.add_argument(
        "--require-tag",
        action="append",
        default=[],
        help="Require evaluation tag for done condition; repeatable",
    )
    p_loop_run.add_argument(
        "--forbid-tag",
        action="append",
        default=[],
        help="Fail done condition if evaluation tag is present; repeatable",
    )
    p_loop_run.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Stop continuing a trace after this many prior evaluations",
    )
    p_loop_run.add_argument(
        "--all", action="store_true", help="Re-evaluate traces that already have evaluations"
    )
    p_loop_run.add_argument(
        "--no-distill-failures",
        action="store_true",
        help="Do not create proposals for traces below min-score",
    )
    p_loop_run.add_argument("--limit", type=int, default=None)
    p_loop_run.set_defaults(func=cmd_loop_run)

    p_loop_schedule = loop_sub.add_parser("schedule", help="Write a project-local loop schedule")
    p_loop_schedule.add_argument(
        "--interval", choices=["hourly", "daily", "weekly"], default="daily"
    )
    p_loop_schedule.add_argument("--evaluator", default="rubric")
    p_loop_schedule.add_argument("--min-score", type=int, default=70)
    p_loop_schedule.add_argument(
        "--condition", default=None, help="JSON loop condition persisted into the schedule"
    )
    p_loop_schedule.add_argument("--require-tag", action="append", default=[])
    p_loop_schedule.add_argument("--forbid-tag", action="append", default=[])
    p_loop_schedule.add_argument("--max-iterations", type=int, default=None)
    p_loop_schedule.add_argument(
        "--all", action="store_true", help="Re-evaluate traces that already have evaluations"
    )
    p_loop_schedule.add_argument("--no-distill-failures", action="store_true")
    p_loop_schedule.add_argument("--limit", type=int, default=None)
    p_loop_schedule.set_defaults(func=cmd_loop_schedule)

    p_loop_status = loop_sub.add_parser("status", help="Show current project-local loop schedule")
    p_loop_status.set_defaults(func=cmd_loop_status)

    p_loop_tick = loop_sub.add_parser(
        "tick", help="Run scheduled loop if due, updating last/next run times"
    )
    p_loop_tick.add_argument(
        "--force", action="store_true", help="Run even if the schedule is not due"
    )
    p_loop_tick.set_defaults(func=cmd_loop_tick)

    p_controller = sub.add_parser("controller", help="Run and inspect autonomous controller ticks")
    controller_sub = p_controller.add_subparsers(dest="controller_command", required=True)
    p_controller_run = controller_sub.add_parser(
        "run", help="Run one controller tick using .skillloop/policy.json if present"
    )
    p_controller_run.set_defaults(func=cmd_controller_run)
    p_controller_history = controller_sub.add_parser(
        "history", help="List stored controller run summaries"
    )
    p_controller_history.add_argument("--limit", type=int, default=20)
    p_controller_history.set_defaults(func=cmd_controller_history)
    p_controller_show = controller_sub.add_parser(
        "show", help="Show a stored controller run by full id or unique prefix"
    )
    p_controller_show.add_argument("run_id")
    p_controller_show.set_defaults(func=cmd_controller_show)

    p_service = sub.add_parser(
        "service", help="Install, inspect, and remove the local background controller service"
    )
    service_sub = p_service.add_subparsers(dest="service_command", required=True)
    p_service_install = service_sub.add_parser(
        "install", help="Write a platform service definition for recurring controller ticks"
    )
    p_service_install.add_argument(
        "--kind", choices=["launchd"], default=None, help="Service kind (default: launchd on macOS)"
    )
    p_service_install.add_argument(
        "--interval-seconds", type=int, default=3600, help="Controller tick interval in seconds"
    )
    p_service_install.add_argument("--label", default=None, help="Override generated service label")
    p_service_install.add_argument(
        "--launch-agents-dir",
        "--service-dir",
        dest="launch_agents_dir",
        default=None,
        help="Override service definition directory, mainly for tests",
    )
    p_service_install.set_defaults(func=cmd_service_install)
    p_service_status = service_sub.add_parser(
        "status", help="Show recorded service installation metadata"
    )
    p_service_status.add_argument("--json", action="store_true")
    p_service_status.set_defaults(func=cmd_service_status)
    p_service_uninstall = service_sub.add_parser("uninstall", help="Remove recorded service files")
    p_service_uninstall.add_argument(
        "--launch-agents-dir",
        "--service-dir",
        dest="launch_agents_dir",
        default=None,
        help="Override service definition directory, mainly for tests",
    )
    p_service_uninstall.set_defaults(func=cmd_service_uninstall)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except BrokenPipeError:
        return 1


__all__ = ["build_parser", "main"]
