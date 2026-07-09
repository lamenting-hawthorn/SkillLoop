from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from skillloop.adapters.generic_jsonl import load_generic_jsonl
from skillloop.adapters.hermes import list_hermes_state_sessions, load_hermes_state_db
from skillloop.dataset import build_manifest, parse_split_spec, split_records, write_jsonl, write_manifest
from skillloop.dataset_readiness import assess_dataset_readiness
from skillloop.export.dpo import export_dpo_records
from skillloop.export.sft import export_sft_records
from skillloop.fs_safety import atomic_write_json, ensure_not_symlink_escape, resolve_under_root, safe_path_segment
from skillloop.loop import LoopRunSummary, run_outer_loop
from skillloop.policy import SkillLoopPolicy
from skillloop.sanitize import redact_for_report
from skillloop.schema import AgentTrace, Evaluation, Proposal, now_iso, sha256_text, stable_json_dumps
from skillloop.store import SkillLoopStore


@dataclass
class ControllerRunReport:
    id: str = ""
    started_at: str = field(default_factory=now_iso)
    finished_at: str | None = None
    policy: dict[str, Any] = field(default_factory=dict)
    actions: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def finish(self) -> None:
        self.finished_at = now_iso()
        if not self.id:
            self.id = sha256_text(stable_json_dumps({"started_at": self.started_at, "actions": self.actions, "errors": self.errors}))[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "policy": self.policy,
            "actions": self.actions,
            "errors": self.errors,
            "summary": self.summary,
        }


def controller_runs_dir(store: SkillLoopStore) -> Path:
    store.init()
    return ensure_not_symlink_escape(store.state_dir / "controller_runs", store.state_dir, label="controller runs directory")


def save_controller_report(store: SkillLoopStore, report: ControllerRunReport) -> Path:
    store.init()
    if report.finished_at is None:
        report.finish()
    report_id = safe_path_segment(report.id, label="controller report id")
    out = ensure_not_symlink_escape(controller_runs_dir(store) / f"{report_id}.json", controller_runs_dir(store), label="controller report output")
    out.parent.mkdir(parents=True, exist_ok=True)
    report.errors = [redact_for_report(err, pii=True) for err in report.errors]
    payload = report.to_dict()
    atomic_write_json(out, payload)
    store.save_controller_run(payload)
    return out


def _evaluations_by_trace(store: SkillLoopStore, traces: list[AgentTrace]) -> dict[str, Evaluation]:
    return store.latest_evaluations({trace.id for trace in traces})


def _proposals_by_trace(store: SkillLoopStore, traces: list[AgentTrace]) -> dict[str, list[Proposal]]:
    wanted = {trace.id for trace in traces}
    result = {trace.id: [] for trace in traces}
    for proposal in store.list_proposals(status=None):
        if proposal.trace_id in wanted:
            result[proposal.trace_id].append(proposal)
    return result


def _ingested_hermes_session_ids(store: SkillLoopStore) -> set[str]:
    session_ids: set[str] = set()
    for trace in store.list_traces():
        if trace.source != "hermes_state_db":
            continue
        session_id = trace.metadata.get("session_id")
        if session_id:
            session_ids.add(str(session_id))
    return session_ids


def _passes_dataset_gate(evaluation: Evaluation, policy: SkillLoopPolicy) -> bool:
    if evaluation.score < policy.dataset.min_score:
        return False
    result = (evaluation.run_condition or {}).get("result")
    if isinstance(result, dict) and "passed" in result:
        return bool(result["passed"])
    return policy.evaluation.condition.evaluate(evaluation, prior_iterations=0).passed


def ingest_from_policy(store: SkillLoopStore, policy: SkillLoopPolicy) -> list[str]:
    ingestion = policy.ingestion
    if not ingestion.enabled:
        return []
    saved: list[str] = []
    if ingestion.adapter == "generic":
        for path in ingestion.paths:
            trace = load_generic_jsonl(path)
            saved.append(store.save_trace(trace))
    elif ingestion.adapter == "hermes-db":
        if not ingestion.hermes_db_path:
            raise ValueError("ingestion.hermes_db_path is required for hermes-db adapter")
        if ingestion.latest:
            trace = load_hermes_state_db(ingestion.hermes_db_path, latest=True)
            session_id = str(trace.metadata.get("session_id") or "")
            if session_id not in _ingested_hermes_session_ids(store):
                saved.append(store.save_trace(trace))
        else:
            already_seen = _ingested_hermes_session_ids(store)
            for session_id in list_hermes_state_sessions(ingestion.hermes_db_path, limit=ingestion.max_sessions):
                if session_id in already_seen:
                    continue
                trace = load_hermes_state_db(ingestion.hermes_db_path, session_id=session_id)
                saved.append(store.save_trace(trace))
    elif ingestion.adapter in {"none", ""}:
        return []
    else:
        raise ValueError(f"unsupported ingestion adapter in policy: {ingestion.adapter}")
    return saved


def export_dataset_from_policy(store: SkillLoopStore, policy: SkillLoopPolicy) -> dict[str, Any] | None:
    dataset = policy.dataset
    if not (dataset.enabled or dataset.auto_update):
        return None
    all_traces = store.list_traces()
    latest_evaluations = store.latest_evaluations({trace.id for trace in all_traces})
    traces = []
    for trace in all_traces:
        latest = latest_evaluations.get(trace.id)
        if latest is not None and _passes_dataset_gate(latest, policy):
            traces.append(trace)
    evaluations = _evaluations_by_trace(store, traces)
    proposals = _proposals_by_trace(store, traces)
    if dataset.kind == "sft":
        records = export_sft_records(traces, evaluations_by_trace=evaluations, proposals_by_trace=proposals)
    elif dataset.kind == "dpo":
        records = export_dpo_records(traces, evaluations_by_trace=evaluations, proposals_by_trace=proposals)
    else:
        raise ValueError(f"unsupported dataset kind: {dataset.kind}")

    split_spec = parse_split_spec(dataset.splits)
    split_map = split_records(records, split_spec)
    readiness = assess_dataset_readiness(
        split_records_map=split_map,
        source_traces=traces,
        evaluations_by_trace=evaluations,
    )
    out = resolve_under_root(store.root, dataset.out, label="controller dataset output")
    output_files: dict[str, Path] = {}
    if len(split_map) == 1 and "train" in split_map:
        output_files["train"] = write_jsonl(out, split_map["train"])
    else:
        for split_name, split_items in split_map.items():
            split_path = out.with_name(f"{out.stem}.{split_name}{out.suffix or '.jsonl'}")
            output_files[split_name] = write_jsonl(split_path, split_items)
    manifest = build_manifest(
        kind=dataset.kind,
        split_outputs=output_files,
        split_records_map=split_map,
        source_traces=traces,
        evaluations_by_trace=evaluations,
        proposals_by_trace=proposals,
        export_metadata={
            "min_score": dataset.min_score,
            "split_spec": dataset.splits,
            "controller_managed": True,
            "auto_update": dataset.auto_update,
            "condition": policy.evaluation.condition.to_dict(),
            "readiness": readiness.to_dict(),
        },
    )
    manifest_path = out.with_suffix(out.suffix + ".manifest.json")
    write_manifest(manifest_path, manifest)
    return {
        "kind": dataset.kind,
        "records": manifest.records,
        "estimated_tokens": manifest.estimated_tokens,
        "output_files": {name: str(path) for name, path in output_files.items()},
        "manifest": str(manifest_path),
        "readiness": readiness.to_dict(),
    }


def controller_tick(store: SkillLoopStore, policy: SkillLoopPolicy) -> ControllerRunReport:
    store.init()
    report = ControllerRunReport(policy=policy.to_dict())
    try:
        ingested = ingest_from_policy(store, policy)
        report.actions.append({"type": "ingest", "count": len(ingested), "trace_ids": ingested})
    except Exception as exc:  # noqa: BLE001 - controller must report and continue to safe later stages
        report.errors.append(redact_for_report(f"ingest:{type(exc).__name__}:{exc}", pii=True))

    evaluation_policy = policy.evaluation
    loop_summary: LoopRunSummary = run_outer_loop(
        store,
        evaluator=evaluation_policy.evaluator,
        min_score=evaluation_policy.min_score,
        condition=evaluation_policy.condition,
        only_unevaluated=evaluation_policy.only_unevaluated,
        distill_failures=evaluation_policy.distill_failures,
        limit=evaluation_policy.limit,
    )
    report.actions.append({"type": "evaluate", **loop_summary.to_dict()})

    try:
        dataset_summary = export_dataset_from_policy(store, policy)
        if dataset_summary is not None:
            report.actions.append({"type": "dataset_export", **dataset_summary})
    except Exception as exc:  # noqa: BLE001
        report.errors.append(redact_for_report(f"dataset:{type(exc).__name__}:{exc}", pii=True))

    report.summary = {
        "errors": len(report.errors),
        "traces_seen": loop_summary.traces_seen,
        "traces_evaluated": loop_summary.traces_evaluated,
        "proposals_created": loop_summary.proposals_created,
        "requires_review": len(store.list_proposals(status="pending")),
    }
    report.finish()
    save_controller_report(store, report)
    return report
