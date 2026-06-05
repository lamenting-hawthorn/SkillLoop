# Safety Model

SkillLoop handles agent traces, memory candidates, skill candidates, and training data. These can contain sensitive information, so the MVP is intentionally conservative.

## Core safety principles

1. Local-first by default
2. Review before apply
3. No global agent mutation in v1
4. No credential storage
5. Generated artifacts are ignored by git

## Local state

SkillLoop writes local state under the selected project root:

```text
.skillloop/skillloop.db
```

Approved exports are also project-local:

```text
.skillloop/approved/memory/*.md
.skillloop/approved/skill/*.md
```

Training exports are written only to user-selected output paths.

## Hermes separation

SkillLoop does not write into:

```text
~/.hermes/memories
~/.hermes/skills
~/.hermes/config.yaml
```

Hermes can be a trace source, but SkillLoop v1 remains a separate export/review layer.

## Review queue

Distillation produces proposals. Proposals stay pending until explicitly approved or rejected.

This prevents accidental mutation from noisy traces, hallucinated lessons, or one-off task state.

## Credentials

The repository ignores local env and state files:

```text
.env
.env.*
.skillloop/
data/*.jsonl
```

The MVP does not require API keys or cloud credentials.

## Trace privacy

Agent traces may contain private content. Before sharing datasets produced by SkillLoop:

- inspect generated JSONL files
- remove personal data and credentials
- avoid exporting private conversations without consent
- prefer synthetic or sanitized examples for public repos

## Known limitations

The MVP has deterministic heuristics and basic secret avoidance. It is not a complete DLP system.

Recommended future hardening:

- configurable redaction before storage
- allow/deny path policies for adapters
- dataset review reports
- PII detection
- secret scanning in CI
