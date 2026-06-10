# SkillLoop Next Steps

Current product direction: SkillLoop is not a user-operated CLI workflow. It is a local autonomous learning sidecar for Hermes-like agent harnesses.

Critical architecture rule: Hermes is the source-of-truth runtime substrate. SkillLoop must not duplicate Hermes memory, skills, tracing, cron, tools, gateway, or subagent systems. SkillLoop is the learning governor over those existing Hermes artifacts.

User-facing model:

```text
User talks to Hermes normally
  -> Hermes emits traces/events
  -> SkillLoop runs locally in the background
  -> SkillLoop ingests, evaluates, distills, updates datasets, judges readiness
  -> User only sees approvals, important summaries, or status
```

## P0: Autonomous Controller

Goal: convert existing CLI primitives into a policy-driven controller that can run unattended locally.

Tasks:

1. Add policy schema/config.
   - File: `skillloop/policy.py`
   - Default policy should be conservative and review-first.
   - Policy controls ingestion, evaluation, proposals, datasets, training, promotion.

2. Add controller tick.
   - File: `skillloop/controller.py`
   - One tick should execute: ingest configured source -> evaluate -> distill -> update datasets/readiness report.
   - Controller should call existing Python functions, not shell out to CLI.

3. Add run reports.
   - Store every autonomous tick summary locally.
   - Include actions taken, traces seen, evaluations, proposals, dataset state, readiness result, errors, cost placeholder.

4. Add Hermes connector.
   - First connector reads Hermes `state.db` locally as the canonical execution trace source.
   - It must ingest unseen Hermes sessions incrementally, not repeatedly re-ingest only the latest session.
   - Preserve Hermes session IDs, message IDs, source/channel, and timestamps as provenance.
   - Do not create a parallel memory/skill runtime; read Hermes artifacts and produce governed learning objects.
   - Later connector can consume explicit emitted events/webhooks.

5. Add setup/start UX.
   - Target install experience: one or two commands max.
   - Example final UX: `skillloop setup --connect hermes --start`.
   - On macOS, setup should support launchd; on Linux, systemd or cron.

## P1: Dataset Readiness

Goal: SkillLoop should decide when training data is organized enough to propose training.

Tasks:

1. Add dataset judge.
   - Check min records, validation split, average score, low-score count, duplicates, estimated tokens, secret-like content.

2. Add readiness result object.
   - Output: ready/not ready, reasons, stats, recommendation.

3. Integrate readiness into controller.
   - Controller updates datasets automatically, then writes readiness into run report.

## P2: Training Planner, Not Auto-Training Yet

Goal: create training plans automatically when readiness passes, but keep actual training gated.

Tasks:

1. Generate training plan from policy + manifest.
2. Estimate hardware/cost/time where possible.
3. Require approval before any expensive training run.

## P3: Training Runner + Evaluation Harness

Only after P0-P2 are stable.

Tasks:

1. Run Unsloth/TRL/Axolotl jobs under explicit policy gates.
2. Track checkpoints/adapters as model candidates.
3. Evaluate candidate model against baseline.
4. Propose promotion only if candidate wins and no safety regression appears.

## Non-goals right now

- Do not make users manually orchestrate the pipeline.
- Do not duplicate Hermes memory, skills, session tracing, cron, gateway, tools, or subagent systems.
- Do not auto-finetune before readiness, cost, evaluation, and promotion gates exist.
- Do not auto-promote models into Hermes.
- Do not write into global Hermes memory/skills without explicit approval.
