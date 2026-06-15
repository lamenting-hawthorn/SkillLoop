# Safety Model

SkillLoop handles agent traces, memory candidates, skill candidates, dataset records, training manifests, and training configuration artifacts. These can contain sensitive or proprietary information, so the project is intentionally conservative.

## Core safety principles

1. Local-first by default.
2. Read-only runtime integration.
3. Review before apply.
4. No global Hermes mutation in v1.
5. Redact obvious secrets during ingestion and export.
6. Do not store credentials.
7. Generated artifacts and local state are ignored by git.
8. Training configs may be generated, but training does not auto-run.
9. Promotion of memories, skills, prompts, or models must be explicit and review-gated.

## Local state

SkillLoop writes project-local state under the selected `--path` root:

```text
.skillloop/skillloop.db
.skillloop/policy.json
.skillloop/controller_runs/*.json
.skillloop/raw_traces/*
.skillloop/approved/memory/*.md
.skillloop/approved/skill/*.md
```

Training exports and benchmark reports are written only to user-selected output paths.

## Hermes separation

SkillLoop does not write into:

```text
~/.hermes/memories
~/.hermes/skills
~/.hermes/config.yaml
~/.hermes/cron
```

Hermes can be a trace source, but SkillLoop v1 remains a separate export/review layer. The Hermes `state.db` adapter uses read-only SQLite access.

## Review queue

Distillation produces proposals. Proposals stay pending until explicitly approved or rejected.

This prevents accidental mutation from noisy traces, hallucinated lessons, one-off task state, private content, or stale facts.

## Proposal apply boundary

`skillloop apply` writes approved proposals only under:

```text
.skillloop/approved/
```

These are export artifacts, not live Hermes memories or skills.

## Dataset and training safety

Dataset export is a preparation step. It does not train a model.

SFT/DPO exports include manifests with:

- record counts
- estimated tokens
- split summaries
- source trace IDs
- evaluation provenance
- proposal provenance summaries

DPO export is conservative and only emits explicit chosen/rejected preference pairs already present in trace metadata.

Training config generation creates configuration files for TRL, Unsloth, and Axolotl. It does not run training and includes explicit no-auto-run metadata.

## Credentials and redaction

SkillLoop redacts common secret patterns during generic/Hermes ingestion and SFT/DPO export, including obvious `sk-...` keys, bearer tokens, and `api_key`/`token`/`secret`/`password` assignments.

Redaction is a safety net, not a complete DLP system. Do not feed private production traces into public datasets without inspection.

The repository ignores local env and state files:

```text
.env
.env.*
.skillloop/
data/*.jsonl
.worktrees/
docs/HANDOFF.md
```

The current MVP does not require API keys or cloud credentials.

## Trace privacy

Agent traces may contain private content. Before sharing data produced by SkillLoop:

- inspect generated JSONL files
- inspect dataset manifests
- remove personal data and credentials
- avoid exporting private conversations without consent
- prefer synthetic or sanitized examples for public demonstrations

## Licensing and usage boundary

This repository is proprietary and all rights are reserved. Viewing the source does not grant permission to use, copy, distribute, host, train on, or create derivative works from it. See `LICENSE`.

## Known limitations

The current system has deterministic heuristics and common-pattern redaction. It is not a complete safety or DLP system.

Recommended hardening:

- configurable redaction policies before storage
- allow/deny path policies for adapters
- dataset readiness reports
- PII detection
- evaluator staleness detection
- cost tracking before LLM evaluators
- secret scanning in CI
- stronger evidence-trust scoring
