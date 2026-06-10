# SkillLoop — Hand-Off Document

**Last updated:** 2026-06-10
**Repository:** https://github.com/lamenting-hawthorn/skillloop

This document is the single source of truth for SkillLoop's state, direction, and
outstanding work. Read it at the start of any new session to pick up where we left
off. Update it at the end of every meaningful session before committing.

---

## 1. What SkillLoop Is (Context for New Sessions)

SkillLoop is a **local autonomous learning sidecar for Hermes**. The user talks to
Hermes normally. SkillLoop runs in the background, watches Hermes's execution
history, and turns good/bad experiences into governed learning artifacts.

**Critical architecture rule:** Hermes is the source-of-truth runtime substrate.
SkillLoop must NOT duplicate Hermes memory, skills, tracing, cron, tools, gateway,
or subagent systems. SkillLoop is the **learning governor** over those existing
Hermes artifacts.

Target UX:

```text
User talks to Hermes normally
  -> Hermes stores sessions/traces in state.db
  -> SkillLoop runs locally in the background
  -> SkillLoop ingests unseen Hermes sessions
  -> SkillLoop evaluates, distills, updates datasets, judges readiness
  -> User only sees approvals, important summaries, or status
```

Target setup UX: one or two commands max.

```bash
skillloop setup --connect hermes --start
```

---

## 2. Current System State

### 2.1 What is implemented (done)

| Layer | Files | Status |
|-------|-------|--------|
| Trace ingestion | `adapters/hermes.py`, `adapters/generic_jsonl.py` | Can read Hermes `state.db` incrementally (unseen sessions only) and JSONL exports |
| Schema | `schema.py` | `AgentTrace`, `AgentMessage`, `ToolCall`, `Evaluation`, `Proposal` with full provenance fields |
| Persistence | `store.py` | SQLite-backed `.skillloop/skillloop.db` |
| Evaluation | `eval/rubric.py`, `eval/legacy.py`, `eval/registry.py`, `eval/evidence.py` | Deterministic rubric + legacy for benchmarks; structured evidence with tool/file/user feedback tracking |
| Proposal distillation | `distill/memory.py`, `distill/skills.py` | Heuristic memory and skill proposal generation |
| Proposal lifecycle | `review/queue.py`, `apply/filesystem.py` | Review queue (approve/reject/list), local apply under `.skillloop/approved/` |
| Provenance | `provenance.py` | Component provenance with SHA256 hashing; evaluations and proposals carry source hashes |
| Dataset export | `export/sft.py`, `export/dpo.py`, `dataset.py` | SFT JSONL, DPO JSONL (conservative), train/val/test splits, manifests with token estimates |
| Training config | `training_config.py` | Unsloth, TRL, Axolotl config generation with explicit `auto_run=false` safety |
| Benchmarking | `benchmark.py` | Replay benchmark comparing evaluator versions |
| Outer loop | `loop.py` | Schedule, tick, declarative done/stopped/failing conditions |
| Condition engine | `conditions.py` | `score_gte`, `required_tags`, `forbidden_tags`, `max_iterations` |
| Policy | `policy.py` | `SkillLoopPolicy` with ingestion/evaluation/dataset/training sections; default conservative |
| Controller | `controller.py` | `controller_tick()`: ingest->eval->distill->export->report. Incremental Hermes DB ingestion |
| CLI | `cli.py` | Full CLI for all commands |
| Tests | `tests/` | 54 tests, all passing |
| Secret redaction | `sanitize.py` | Pattern-based API key/token/password redaction during ingestion and export |

### 2.2 Architecture diagram

```text
Hermes state.db (sessions, messages, tool_calls)
        |
        v
  [adapters/hermes.py]  -- read-only, incremental ingestion
        |
        v
  [store.py]  -- SQLite persistence of traces, evaluations, proposals
        |
        v
  [eval/registry.py + eval/rubric.py]  -- deterministic scoring with evidence
        |
        v
  [distill/memory.py + distill/skills.py]  -- proposals with provenance
        |
        v
  [review/queue.py + apply/filesystem.py]  -- human-gated approval
        |
   +--> [export/sft.py, export/dpo.py]  -- training datasets
   |        |
   |        v
   |    [dataset.py]  -- manifests, splits, token estimates
   |        |
   |        v
   |    [training_config.py]  -- Unsloth/TRL/Axolotl configs (auto_run=false)
   |
   +--> [policy.py + controller.py + loop.py]  -- autonomous controller
            |
            v
        [controller_runs/]  -- run reports
```

---

## 3. Short-Term Tasks (P0 — active)

Goal: make SkillLoop a real local sidecar with setup/start UX.

### 3.1 Setup/start UX (P0.1)

**Current state:** Policy and controller code exist but the user must still manually
configure and run commands.

**Needed:**

- [ ] `skillloop setup --connect hermes --start`
  - Detect `~/.hermes/state.db`
  - Create `.skillloop/policy.json` with conservative defaults
  - Set ingestion adapter to `hermes-db`
  - Run one controller tick
  - Install/start background service

- [ ] `skillloop status` — show current state, last run, pending proposals, dataset stats

- [ ] Background service runner:
  - macOS: launchd plist generation
  - Linux: systemd unit or cron job

**Files likely touched:** `cli.py`, new `install.py` or `setup.py`, new launchd/systemd template files.

---

### 3.2 Controller run history (P0.2)

**Current state:** Controller writes run reports under `.skillloop/controller_runs/`, but there is no inspection command.

**Needed:**

- [ ] `skillloop controller history` — list past runs with summary
- [ ] `skillloop controller show <id>` — full run detail
- [ ] Store runs in SQLite alongside traces/evaluations

**Files likely touched:** `controller.py`, `store.py`, `schema.py`, `cli.py`.

---

### 3.3 Auto-export on controller tick (P0.3)

**Current state:** Controller calls dataset export but only when policy explicitly enables it. The dataset readiness layer does not exist yet.

**Needed:**

- [ ] Controller tick should update SFT dataset automatically if `datasets.sft.auto_update: true`
- [ ] Dataset should only include traces that pass eval condition

---

## 4. Long-Term Tasks (P1–P3)

### 4.1 Dataset Readiness Judge (P1)

**Goal:** SkillLoop should decide when training data is organized enough to propose training.

**Needed:**

- [ ] Minimum record count check
- [ ] Minimum estimated tokens
- [ ] Validation split required
- [ ] Average evaluation score threshold
- [ ] Low-score record cap
- [ ] Duplicate/near-duplicate checks
- [ ] Secret-like content scan
- [ ] Explicit recommendation output: `ready`, `collect_more_data`, `blocked`

**Files likely:** new `dataset_judge.py`, integration into `controller.py`.

---

### 4.2 Training Planner (P2)

**Goal:** Create training plans automatically when readiness passes. Keep actual training gated.

**Needed:**

- [ ] Training plan object
  - Target library: Unsloth, TRL, Axolotl
  - Base model
  - Dataset manifest
  - Hyperparameters
  - Expected output paths
  - Cost/time/hardware estimates where available
  - Approval requirement flag

- [ ] `skillloop training plan` command

**Files likely:** new `training_plan.py`, extension of `training_config.py`.

---

### 4.3 Training Runner + Evaluation Harness (P3)

**Only after P0–P2 are stable.**

**Needed:**

- [ ] Training runner
  - Manual/approved execution only at first
  - Captures logs, exit status, checkpoint paths, runtime, cost placeholder
  - Never stores hub tokens or credentials in SkillLoop state

- [ ] Candidate model registry
  - Base model identity
  - Adapter/checkpoint path
  - Dataset manifest used
  - Training config used
  - Training run ID
  - Provenance hashes

- [ ] Evaluation harness
  - Compare candidate against baseline
  - Use held-out validation traces and regression prompts
  - Report improvements, regressions, safety failures

- [ ] Promotion policy
  - No auto-promotion initially
  - Promotion becomes a reviewed proposal
  - Require minimum score improvement and no critical regression

---

## 5. Known Issues / Gaps

### 5.1 Engineering gaps

- **Cost tracking:** No per-run or per-trace cost tracking. Must add before LLM evaluators.
- **Error handling:** If one trace errors during loop tick, the whole tick may not recover gracefully.
- **No evaluator-component-change re-ingestion:** If evaluator hash changes, old evaluations are not automatically flagged as stale.
- **DPO conservative only:** DPO export only works when explicit preference pairs already exist in trace metadata. No automatic chosen/rejected generation.
- **Skill distiller basic:** Skill proposal generation uses simple heuristics, not deep trace analysis.
- **No real cron/daemon integration:** The loop exists in code but there is no `skillloop daemon` or automated cron registration.
- **uv.lock exists but pyproject.toml uses setuptools:** uv.lock was accidentally created in the tree; repo does not use uv.

### 5.2 Non-goals (do NOT implement yet)

- Do NOT auto-finetune before readiness, cost, evaluation, and promotion gates exist.
- Do NOT auto-promote models into Hermes.
- Do NOT write into global Hermes memory/skills without explicit approval.
- Do NOT duplicate Hermes memory, skills, session tracing, cron, gateway, tools, or subagent systems.
- Do NOT make users manually orchestrate the pipeline.

---

## 6. Architecture Rules (Recurring Principles)

1. **Hermes is the runtime; SkillLoop is the governor.** Never rebuild Hermes subsystems.
2. **Review-first.** No automatic global mutation. Approvals required for memory/skills/training/promotion.
3. **Provenance everywhere.** Every evaluation, proposal, dataset, and training artifact must carry source hashes.
4. **Conservative DPO.** Only export explicitly provided preference pairs.
5. **Deterministic evaluator first.** LLM evaluators only after cost tracking exists.
6. **Cost-conscious.** Estimate tokens, storage, and compute before scaling. Bounded defaults.
7. **Local-first.** No cloud dependency. State lives in `.skillloop/`.
8. **CLI is admin surface, not user product.** Normal users talk to Hermes.

---

## 7. Repository Layout

```text
skillloop/
  adapters/        Hermes state.db + generic JSONL ingestion
  apply/           Review-approved filesystem exports
  distill/         Memory and skill proposal generation
  eval/            Evaluator registry, deterministic rubric, legacy, evidence
  export/          SFT and DPO dataset exporters
  review/          Proposal review queue helpers
  benchmark.py     Replay benchmark comparing evaluator versions
  cli.py           Command-line interface (admin/debug surface)
  conditions.py    Declarative run/done conditions
  controller.py    Autonomous controller tick
  dataset.py       Dataset split, manifest, provenance, and stats helpers
  loop.py          Outer loop scheduling
  policy.py        Policy schema and defaults
  provenance.py    Component provenance with SHA256 hashing
  sanitize.py      Secret redaction
  schema.py        Trace/Evaluation/Proposal dataclasses
  store.py         SQLite persistence
  training_config.py  Unsloth/TRL/Axolotl config generation
tests/             Pytest suite (54 tests)
docs/
  architecture.md  System design
  cli.md           Command reference
  safety.md        Safety boundaries
  trace-schema.md  Data format
```

---

## 8. Session Hand-Off Protocol

At the end of every session where progress was made:

1. Update the "What is implemented" table (section 2.1).
2. Check off completed items in short-term/long-term sections.
3. Add any new issues to "Known Issues / Gaps" (section 5).
4. Update the "Last updated" date at the top.
5. Commit with message like `docs: update hand-off document`.

At the start of every new session:

1. Read this document top to bottom.
2. Check `git log --oneline -10` for any commits since the last update.
3. Run `python -m pytest -q` to confirm test baseline.
4. Pick up from the first unchecked item in section 3 (short-term).

---

## 9. Related Hermes Skills

These operational skills live in `~/.hermes/skills/system/` and complement
SkillLoop's loop engineering work. They handle the Hermes runtime side
(SkillLoop is the governor, Hermes is the runtime — Rule #1).

| Skill | Path | Purpose |
|-------|------|---------|
| `pre-loop-checklist` | `system/pre-loop-checklist/` | 4-condition test + 30-second check before creating cron jobs |
| `cron-job-workflows` | `system/cron-job-workflows/` | Cron patterns + STATE.md + Ralph Wiggum detection + Red Flags |
| `goal-loop` | `system/goal-loop/` | /goal primitive: cron jobs that run until objective condition met |

See `docs/analysis/loop-engineering-analysis.md` section 8 for full details on
what each skill contains and how they were derived from the loop engineering
framework.
