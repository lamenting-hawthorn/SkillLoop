from __future__ import annotations

import argparse
import json
from pathlib import Path

from skillloop.interfaces.cli._shared import _format_count, _load_policy, _policy_path, _store


def cmd_status(args: argparse.Namespace) -> int:
    store = _store(args)
    store.init()
    policy_path = _policy_path(store)
    traces = store.list_traces()
    evaluations = store.list_evaluations()
    pending = store.list_proposals(status="pending")
    runs = store.list_controller_runs(limit=1)
    policy = _load_policy(store)
    dataset_manifest = (store.root / policy.dataset.out).resolve().with_suffix(Path(policy.dataset.out).suffix + ".manifest.json")
    dataset_stats = None
    if dataset_manifest.exists():
        try:
            manifest = json.loads(dataset_manifest.read_text(encoding="utf-8"))
            dataset_stats = {
                "manifest": str(dataset_manifest),
                "records": manifest.get("records", 0),
                "estimated_tokens": manifest.get("estimated_tokens", 0),
            }
        except (json.JSONDecodeError, OSError) as exc:
            dataset_stats = {
                "manifest": str(dataset_manifest),
                "records": 0,
                "estimated_tokens": 0,
                "error": f"failed to load manifest: {exc}",
            }
    status = {
        "root": str(store.root),
        "state_dir": str(store.state_dir),
        "policy": str(policy_path) if policy_path.exists() else None,
        "traces": len(traces),
        "evaluations": len(evaluations),
        "pending_proposals": len(pending),
        "dataset": dataset_stats,
        "last_controller_run": runs[0] if runs else None,
    }
    if args.json:
        print(json.dumps(status, indent=2, ensure_ascii=False))
    else:
        print(f"SkillLoop status for {store.root}")
        print(f"state: {store.state_dir}")
        print(f"policy: {policy_path if policy_path.exists() else 'not configured'}")
        print(_format_count("traces", len(traces)))
        print(_format_count("evaluations", len(evaluations)))
        print(_format_count("pending proposals", len(pending)))
        if dataset_stats:
            if dataset_stats.get("error"):
                print(f"dataset: error={dataset_stats['error']} manifest={dataset_stats['manifest']}")
            else:
                print(
                    f"dataset: records={dataset_stats['records']} "
                    f"estimated_tokens={dataset_stats['estimated_tokens']} manifest={dataset_stats['manifest']}"
                )
        else:
            print("dataset: none")
        if runs:
            run = runs[0]
            summary = run.get("summary", {})
            print(f"last controller run: {run.get('id')} finished={run.get('finished_at')} errors={summary.get('errors')}")
        else:
            print("last controller run: none")
    return 0


__all__ = ["cmd_status"]
