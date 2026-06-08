# Architecture

SkillLoop is a standalone learning loop for agent runtimes. It is designed as a sidecar layer: the runtime executes work, while SkillLoop reads completed traces and turns them into reviewed learning artifacts.

## Design goals

- Runtime-agnostic trace ingestion
- Stable internal schema
- Local-first persistence
- Review-before-apply workflow
- Clean separation from global agent state
- Fine-tuning export without direct training orchestration

## Pipeline

```text
agent trace
   |
   v
ingest adapter
   |
   v
normalized AgentTrace
   |
   +--> SQLite store
   |
   +--> evaluation -> Evaluation
   |
   +--> distillation -> Proposal(memory|skill|dataset)
                           |
                           v
                    review queue
                           |
                    approve/reject
                           |
                           v
                    local approved exports
                           |
                           v
                    SFT/DPO JSONL datasets
```

## Core modules

### `skillloop.schema`

Defines the normalized dataclasses used across the project:

- `AgentMessage`
- `ToolCall`
- `AgentTrace`
- `Evaluation`
- `Proposal`

Adapters should convert runtime-specific formats into these types as early as possible.

### `skillloop.store`

Owns local SQLite persistence under `.skillloop/skillloop.db` in the selected project root.

The store persists:

- traces
- evaluations
- proposals

The store does not write to global Hermes state or any other runtime state.

### `skillloop.adapters`

Adapters translate source traces into `AgentTrace`.

Current MVP adapters:

- `generic_jsonl`: simple JSONL message streams
- `hermes`: Hermes-like JSON and JSONL exports

### `skillloop.eval`

The MVP evaluation engine is deterministic. It scores traces based on observable signals such as:

- final answer presence
- errors and tool failures
- success indicators
- user correction signals

This keeps the MVP offline and reproducible. LLM judges can be added later as optional plugins.

### `skillloop.distill`

Distillation creates learning proposals:

- memory proposals for durable facts, preferences, and conventions
- skill proposals for reusable workflows

Distillation does not directly mutate memory or skills. It writes proposals to the review queue.

### `skillloop.review`

Review helpers list, approve, and reject proposals.

Approval is explicit and prefix-addressable so users can approve generated IDs without copying full UUIDs.

### `skillloop.apply`

The MVP apply step writes approved artifacts into the project-local export area:

```text
.skillloop/approved/memory/*.md
.skillloop/approved/skill/*.md
```

It intentionally does not write into `~/.hermes`.

### `skillloop.export`

Dataset exporters produce JSONL files for later training workflows:

- SFT: `{ "messages": [...] }`
- DPO: `{ "prompt": ..., "chosen": ..., "rejected": ... }`

The exporter is a data preparation step only. It does not launch training.

## Boundary with Hermes

Hermes is one possible source runtime. SkillLoop may ingest Hermes-like traces, but v1 does not mutate Hermes memories, skills, config, or source code.

This boundary makes the project safe to open source, test, and evolve independently.
