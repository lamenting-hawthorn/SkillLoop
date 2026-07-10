# Checkpoint/Replay for SkillLoop Loops — Technical Design

**Date:** 2026-06-21
**Status:** Design complete — pending implementation (P1)
**Estimated effort:** 2-3 days (52 lines of new code)
**Dependencies:** None (uses existing SQLite in `store.py`)

---

## Design Decision: SQLite, Not Temporal/Redis

| Option | Verdict | Why |
|--------|---------|-----|
| **Temporal** | ✗ Wrong tool | Durable execution engine for multi-day, multi-service workflows. Adds a server, worker process, protobuf schemas, and a Temporal cluster dependency. SkillLoop's loop finishes in seconds-to-minutes and runs on a single machine. Temporal replay assumes deterministic functions — LLM calls violate that assumption. |
| **Redis** | ✗ Overkill | In-memory KV store. Adds a second database, a network call, and AOF persistence config. SkillLoop is already local-first SQLite. The only ephemeral state is `LoopRunSummary` and the loop index. |
| **SQLite checkpoints** | ✓ Correct | Two new methods on `SkillLoopStore`, one new table, ~6 lines in the loop. No new servers, no new deps, no network calls. Uses the same SQLite that already stores traces, evaluations, proposals, and controller runs. |

**Replay semantic:** SkillLoop replay means *resumption of stateful progress*, not *deterministic reproduction of identical outputs*. LLM outputs are stochastic — true deterministic replay is impossible. We checkpoint *loop progress* (which trace we're on, accumulated summary), not LLM outputs.

---

## What State Gets Checkpointed

| Field | Why |
|-------|-----|
| `run_id` | Controller run ID — links checkpoint to the `controller_runs` table |
| `trace_index` | Which trace to resume from (0-indexed into `store.list_traces()`) |
| `summary_payload` | Full `LoopRunSummary.to_dict()` — preserves accumulated counts, failing traces, evaluations, proposals |
| `params_hash` | SHA256 of evaluator name + min_score + condition — prevents resuming with different config |
| `status` | `running` \| `awaiting_review` \| `completed` — determines what resume does next |

**What is NOT checkpointed:** Traces themselves (already in `traces` table), evaluations (already written to `evaluations` table as the loop progresses), proposals (already written to `proposals` table). These are idempotent — writing them again is a no-op via `INSERT OR REPLACE`.

---

## Code Changes Required

### 1. `skillloop/store.py` — New `checkpoints` table

Add to `SkillLoopStore.init()`:

```python
conn.execute("""
    CREATE TABLE IF NOT EXISTS checkpoints (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        trace_index INTEGER NOT NULL,
        summary_payload TEXT NOT NULL,
        params_hash TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
""")
```

### 2. `skillloop/store.py` — Two new methods

```python
def save_checkpoint(self, checkpoint_id: str, run_id: str, trace_index: int,
                    summary: dict, params_hash: str, status: str) -> str:
    self.init()
    payload = json.dumps({
        "run_id": run_id,
        "trace_index": trace_index,
        "summary": summary,
        "params_hash": params_hash,
        "status": status,
    }, ensure_ascii=False)
    with self._connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO checkpoints (id, run_id, trace_index, summary_payload, params_hash, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (checkpoint_id, run_id, trace_index, payload, params_hash, status, now_iso()),
        )
    return checkpoint_id

def latest_checkpoint(self, run_id: str) -> dict | None:
    self.init()
    with self._connect() as conn:
        row = conn.execute(
            "SELECT payload FROM checkpoints WHERE run_id = ? ORDER BY created_at DESC LIMIT 1",
            (run_id,)
        ).fetchone()
    return json.loads(row[0]) if row else None
```

### 3. `skillloop/loop.py` — Checkpoint inside the loop

Modify `run_outer_loop` to accept an optional `run_id` parameter and checkpoint after each trace:

```python
def run_outer_loop(store, *, evaluator="rubric", min_score=70, condition=None,
                   only_unevaluated=True, distill_failures=True, limit=None,
                   registry=None, run_id=None, resume_from=None):
    # ... existing setup ...
    summary = LoopRunSummary(traces_seen=len(traces))
    
    # Resume from checkpoint if provided
    start_index = 0
    if resume_from is not None:
        checkpoint = store.latest_checkpoint(resume_from)
        if checkpoint and checkpoint["status"] != "awaiting_review":
            start_index = checkpoint["trace_index"]
            summary = LoopRunSummary.from_dict(json.loads(checkpoint["summary_payload"]))
    
    for i, trace in enumerate(traces[start_index:], start=start_index):
        # ... existing evaluation logic ...
        
        # Checkpoint after each trace
        if run_id:
            params_hash = sha256_text(stable_json_dumps({
                "evaluator": evaluator, "min_score": min_score,
                "condition": condition.to_dict(),
            }))
            checkpoint_id = sha256_text(f"{run_id}:{i+1}:{params_hash}")
            store.save_checkpoint(
                checkpoint_id=checkpoint_id,
                run_id=run_id,
                trace_index=i + 1,
                summary=summary.to_dict(),
                params_hash=params_hash,
                status="running",
            )
    
    # Mark checkpoint as completed
    if run_id:
        params_hash = sha256_text(stable_json_dumps({
            "evaluator": evaluator, "min_score": min_score,
            "condition": condition.to_dict(),
        }))
        checkpoint_id = sha256_text(f"{run_id}:done:{params_hash}")
        store.save_checkpoint(
            checkpoint_id=checkpoint_id,
            run_id=run_id,
            trace_index=len(traces),
            summary=summary.to_dict(),
            params_hash=params_hash,
            status="completed",
        )
    
    return summary
```

### 4. `skillloop/controller.py` — Gate interrupt before export

After the loop finishes, if there are pending proposals, checkpoint with `status="awaiting_review"` and stop:

```python
def controller_tick(store, policy):
    # ... existing ingest + evaluate ...
    
    # Check for pending proposals
    pending = store.list_proposals(status="pending")
    if pending:
        store.save_checkpoint(
            run_id=report.id,
            trace_index=0,  # Loop is done; this marks the post-loop pause
            summary=loop_summary.to_dict(),
            params_hash=sha256_text(stable_json_dumps({"action": "awaiting_review"})),
            status="awaiting_review",
        )
        report.actions.append({
            "type": "interrupt",
            "reason": "pending_review",
            "proposal_count": len(pending),
        })
        report.finish()
        save_controller_report(store, report)
        return report  # Stop — do not export dataset
    
    # No pending proposals: continue to dataset export
    # ... existing export logic ...
```

### 5. `skillloop/cli.py` — New `skillloop resume` command

```python
@cli.command()
@click.argument("run_id")
def resume(run_id):
    """Resume a loop from its last checkpoint."""
    store = _get_store()
    checkpoint = store.latest_checkpoint(run_id)
    if checkpoint is None:
        click.echo(f"No checkpoint found for run {run_id}")
        return
    
    if checkpoint["status"] == "awaiting_review":
        # Verify proposals were handled
        pending = store.list_proposals(status="pending")
        if pending:
            click.echo(f"{len(pending)} proposals still pending. Review first: skillloop review")
            return
        # Re-run controller tick from export phase
        click.echo("Resuming from review gate — exporting dataset...")
    else:
        # Resume loop from trace_index
        click.echo(f"Resuming loop from trace {checkpoint['trace_index']}...")
    
    # Re-run controller_tick with the checkpoint context
    # ...
```

---

## User Flow

### Normal operation (no crash)

```
$ skillloop tick
  → controller_tick runs
  → ingest traces
  → run_outer_loop (iterates all traces, checkpoints after each)
  → checkpoint: status=completed
  → dataset export (if no pending proposals)
```

### Crash during loop

```
$ skillloop tick
  → controller_tick runs
  → ingest traces  
  → run_outer_loop (crashes at trace 23 of 50)
  → checkpoint exists at trace_index=23, status=running

$ skillloop resume <run-id>
  → reads checkpoint: trace_index=23
  → verifies params_hash matches
  → resumes from trace 23
  → continues checkpointing after each trace
  → checkpoint: status=completed
  → dataset export
```

### Review gate pause

```
$ skillloop tick
  → controller_tick runs
  → ingest traces
  → run_outer_loop (completes all traces)
  → 5 proposals created, status=pending
  → checkpoint: status=awaiting_review
  → stops — no dataset export yet

$ skillloop review
  [user reviews and approves proposals]

$ skillloop resume <run-id>
  → reads checkpoint: status=awaiting_review
  → verifies no pending proposals remain
  → proceeds to dataset export
  → checkpoint: status=completed
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `skillloop/store.py` | Add `checkpoints` table to `init()`, add `save_checkpoint()` and `latest_checkpoint()` methods |
| `skillloop/loop.py` | Add `run_id` and `resume_from` params to `run_outer_loop`, add checkpoint calls inside loop, add completion checkpoint |
| `skillloop/controller.py` | Add review-gate interrupt: checkpoint `status="awaiting_review"` when pending proposals exist, skip dataset export |
| `skillloop/cli.py` | Add `skillloop resume <run-id>` command |
| `tests/test_loop.py` | Add tests: checkpoint creation, resume from crash, resume from review gate, params_hash mismatch rejection |
| `tests/test_store.py` | Add tests: save_checkpoint, latest_checkpoint, checkpoint deduplication |

---

## Why Not Build This Now

Per the recommendation in `12-deterministic-workflows-recommendation.md`, this is **Phase 2** of the deterministic workflow integration:

| Phase | What | Priority |
|-------|------|----------|
| 1 (now) | Rubric auto-reject gate + interrupt before apply | P0 |
| 2 (this doc) | Checkpoint/replay for loop resilience | P1 |
| 3 (later) | YAML workflow DSL + Mermaid visualization | P3 |
| 4 (much later) | Parallel branches, sub-workflows | P4 |

Checkpointing depends on the rubric auto-reject gate and the interrupt-before-apply mechanism being in place first (Phase 1), because the `status="awaiting_review"` checkpoint only makes sense if there is a review gate to trigger it.

---

## Acceptance Criteria

- [ ] `store.save_checkpoint()` persists checkpoints to SQLite
- [ ] `store.latest_checkpoint()` retrieves the most recent checkpoint for a run
- [ ] `run_outer_loop` checkpoints after each trace when `run_id` is provided
- [ ] `run_outer_loop` resumes from `trace_index` when `resume_from` is provided
- [ ] `params_hash` mismatch raises a clear error (no silent wrong-config resumption)
- [ ] Controller writes `status="awaiting_review"` checkpoint when pending proposals exist
- [ ] `skillloop resume <run-id>` CLI works for both crash recovery and review gate resumption
- [ ] Checkpoints are idempotent (calling resume twice is safe)
- [ ] No new dependencies added to `pyproject.toml`
- [ ] All existing tests pass (checkpointing is additive, not breaking)
