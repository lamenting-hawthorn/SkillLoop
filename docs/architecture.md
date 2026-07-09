# Architecture

SkillLoop is a local learning governor for agent runtimes.

The runtime executes work. SkillLoop reads completed traces, evaluates them, proposes learning artifacts, and prepares reviewed datasets/configs. It is a sidecar, not a replacement runtime.

Current primary runtime integration: Hermes Agent via read-only `state.db` ingestion.

## Design goals

- Runtime-agnostic trace ingestion
- Read-only runtime integration
- Stable normalized trace schema
- Local-first persistence
- Deterministic evaluation before LLM-based judging
- Review-before-apply workflow
- Provenance on every durable artifact
- Clean separation from global agent state
- Fine-tuning data/config generation without automatic training
- Conservative defaults that fail closed around credentials and global mutation

## Non-goals for v1

- Replacing Hermes or another agent runtime
- Writing directly into `~/.hermes/memories`, `~/.hermes/skills`, or global config
- Auto-applying proposed memories/skills/prompts
- Running training automatically
- Promoting model candidates automatically
- Storing credentials or hub tokens
- Requiring cloud infrastructure

## System pipeline

```mermaid
flowchart TD
    A[Runtime trace\nHermes DB / Hermes export / generic JSONL] --> B[Adapter]
    B --> C[Normalized AgentTrace]
    C --> D[(.skillloop/skillloop.db)]
    D --> E[Evaluation registry]
    E --> F[Evaluation\nscore + evidence + provenance]
    F --> G[Distillation]
    G --> H[Proposal\nmemory / skill]
    H --> I[Review queue]
    I -->|approve| J[Approved local export]
    I -->|reject| K[Rejected]
    J --> L[.skillloop/approved]
    D --> M[Dataset export]
    M --> N[SFT/DPO JSONL]
    M --> O[Manifest\nsplits + counts + provenance]
    O --> P[Training config generation\nTRL / Unsloth / Axolotl]
```

## Controller pipeline

The controller is the current autonomous sidecar primitive. A controller tick runs a complete governed pass and records a durable report.

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant Controller
    participant Hermes as Hermes state.db
    participant Store as SkillLoop SQLite
    participant Eval as Evaluator
    participant Distill as Distiller
    participant Export as Dataset Exporter

    User->>CLI: skillloop setup --connect hermes --start
    CLI->>Store: write .skillloop/policy.json
    CLI->>Controller: controller_tick(policy)
    Controller->>Hermes: read unseen sessions (read-only)
    Controller->>Store: save normalized traces
    Controller->>Eval: evaluate traces
    Eval->>Store: save evaluations
    Controller->>Distill: propose learning artifacts
    Distill->>Store: save pending proposals
    Controller->>Export: optional SFT export if policy enables dataset export
    Export->>Store: read scored traces/proposals
    Controller->>Store: save controller run report
```

Controller reports are stored in SQLite and mirrored under `.skillloop/controller_runs/*.json`.

## Core modules

### `skillloop.schema`

Defines the normalized dataclasses used across the project:

- `AgentMessage`
- `ToolCall`
- `AgentTrace`
- `Evaluation`
- `Proposal`

Adapters should convert runtime-specific formats into these types as early as possible.

### `skillloop.adapters`

Adapters translate source traces into `AgentTrace`.

Current public adapters:

- `generic_jsonl`: simple JSONL message streams
- `hermes`: Hermes-like JSON exports
- `hermes_state_db`: read-only ingestion from Hermes `state.db`

Adapter requirements:

- preserve source metadata where practical
- redact common secret patterns
- avoid mutating source runtimes
- preserve raw artifact references and hashes where available

### `skillloop.store`

Owns project-local SQLite persistence under:

```text
.skillloop/skillloop.db
```

The store persists:

- traces
- evaluations
- proposals
- controller run reports

The store does not write to global Hermes state or any other runtime state.

### `skillloop.eval`

The current evaluation engine is deterministic. It scores traces based on observable signals such as:

- final answer presence
- errors and tool failures
- success indicators
- user correction signals
- structured evidence records

LLM judges are intentionally deferred until cost tracking and budget policy exist.

### `skillloop.distill`

Distillation creates learning proposals:

- memory proposals for durable facts, preferences, corrections, and conventions
- skill proposals for reusable workflows

Distillation does not directly mutate memory or skills. It writes proposals to the review queue.

### `skillloop.review`

Review helpers list, approve, and reject proposals.

Approval is explicit and prefix-addressable so users can approve generated IDs without copying full UUIDs.

### `skillloop.apply`

The apply step writes approved artifacts into the project-local export area:

```text
.skillloop/approved/memory/*.md
.skillloop/approved/skill/*.md
```

It intentionally does not write into `~/.hermes`.

### `skillloop.export`

Dataset exporters produce JSONL files for later training workflows:

- SFT: `{ "messages": [...] }`
- DPO: `{ "prompt": ..., "chosen": ..., "rejected": ... }`

Exports include dataset manifests with split-level counts, estimated tokens, and provenance summaries.

### `skillloop.benchmark`

Replay benchmarks compare evaluator versions over stored traces. Use this before changing evaluator behavior or before trusting a new scoring strategy for training data gates.

### `skillloop.training_config`

Generates configuration artifacts for TRL, Unsloth, and Axolotl.

This module does not launch training. Generated configs include explicit no-auto-run safety metadata.

### `skillloop.policy` and `skillloop.controller`

`SkillLoopPolicy` stores controller behavior under `.skillloop/policy.json`:

- ingestion settings
- evaluation settings
- dataset export settings
- training safety settings

`controller_tick()` executes the current governed sidecar pass:

```text
ingest -> evaluate -> distill -> optional dataset export -> report
```

Controller-managed dataset export also attaches a report-only readiness verdict
to the dataset action and manifest metadata. This is intentionally not a hard
export gate yet; it is a signal for humans and future training gates.

### `skillloop.loop` and `skillloop.conditions`

The outer-loop primitives support scheduled local evaluation/distillation passes and declarative done conditions:

- score threshold
- required tags
- forbidden tags
- max iterations

These are local scheduling primitives. Platform service installation is handled separately by `skillloop.service`: on macOS, SkillLoop can write a launchd plist plus `.skillloop/service.json` metadata for recurring controller ticks. The CLI prints the exact `launchctl` commands instead of silently loading or unloading OS services.

## Deployment Model

SkillLoop is deployed as a local sidecar inside or beside a project, not as a
central cloud service. The practical deployment path is:

```bash
python -m pip install -e .
skillloop --path /path/to/project setup --connect hermes --start --auto-export
```

That command creates project-local `.skillloop/` state, configures read-only
Hermes ingestion, runs one controller tick, and optionally produces a
controller-managed dataset manifest.

This is a one-shot setup/run path. Recurring execution is a separate service
installation step.

For recurring macOS use, the service layer can generate launchd metadata:

```bash
skillloop --path /path/to/project service install --kind launchd --interval-seconds 3600
```

SkillLoop does not silently start services. It records metadata and prints the
exact OS command to load or unload the service. Linux service generation is still
future work.

The package supports GitHub CLI installs, wheels, editable checkouts, and both
`skillloop` and `python -m skillloop` entry points. `skillloop doctor` verifies
deployment health. SQLite schema changes migrate in place, and indexed bulk
evaluation reads avoid per-trace export queries.

## Boundary with Hermes

Hermes is the runtime. SkillLoop is the learning governor.

SkillLoop may read Hermes sessions, but v1 does not mutate Hermes memories, skills, config, cron jobs, tools, gateway state, or source code.

This boundary is deliberate: it keeps the learning layer inspectable, reviewable, and reversible.

## Roadmap priorities

1. Improve core learning-loop quality: proposal quality, memory/skill distillation, and evidence links.
2. Build a clean demo/deployment path that proves setup, controller run, status/history, readiness, and optional service install in one or two commands.
3. Polish review/apply UX so approved memories and skills are easy to inspect and use.
4. Add a packaged install path and a local deployment wrapper, while keeping OS service loading explicit.
5. Add evaluator staleness detection when evaluator code/provenance changes.
6. Add stronger evidence-trust scoring so learning artifacts depend on tool/user evidence rather than assistant claims.
7. Add approval-gated training plans only after readiness, cost, evaluation, and promotion gates exist.
8. Add Linux service generation (`systemd` unit or cron) after the macOS launchd path has had more real local use.

The macOS launchd path has passed an isolated real-system smoke test against local Hermes `state.db`: controller tick, status/history/show, dataset manifest generation, service plist generation, service status, and service uninstall all succeeded without loading a persistent OS service.
