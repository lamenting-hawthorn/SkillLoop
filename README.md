# SkillLoop

SkillLoop is a standalone self-improvement harness for agent systems.

It sits beside an agent runtime, ingests completed agent traces, evaluates them, proposes durable memory and reusable skill updates, and exports fine-tuning-ready datasets. It is deliberately separated from Hermes or any other runtime so it can be reviewed, exported, versioned, or embedded without mutating an existing agent installation.

## Why this exists

Most agents can execute tasks, but their learning loop is usually either missing or tightly coupled to one runtime. SkillLoop keeps that loop explicit:

1. ingest traces from an agent
2. normalize them into a stable schema
3. evaluate quality and learning signals
4. distill candidate memory and skill updates
5. require review before applying anything
6. export curated SFT/DPO data for model improvement

The MVP is local-first, stdlib-first, and review-first.

## What SkillLoop does

- Normalizes generic JSONL, Hermes-style exports, and Hermes `state.db` sessions
- Stores traces, evaluations, and proposals in local SQLite
- Scores traces with deterministic heuristics
- Detects durable user preferences, corrections, success signals, and reusable workflows
- Creates memory and skill proposals instead of silently mutating global state
- Applies approved proposals only into the selected project directory
- Exports SFT JSONL and DPO JSONL datasets with optional score gates
- Redacts common secret patterns during ingestion/export

## What SkillLoop does not do in v1

- It does not replace an agent runtime
- It does not fine-tune a model directly
- It does not write into `~/.hermes/memories`, `~/.hermes/skills`, or global agent config
- It does not require cloud services
- It does not store credentials

## Install for local development

```bash
git clone <repo-url>
cd skillloop
python -m pip install -e '.[dev]'
```

SkillLoop requires Python 3.11+.

## Quickstart

Run the sample workflow from the repository root:

```bash
python -m skillloop.cli --path . init
python -m skillloop.cli --path . ingest generic examples/traces/simple_trace.jsonl
python -m skillloop.cli --path . traces list
python -m skillloop.cli --path . eval latest
python -m skillloop.cli --path . distill latest
python -m skillloop.cli --path . review list --verbose
python -m skillloop.cli --path . export sft --out data/sft.jsonl --min-score 70
python -m skillloop.cli --path . export dpo --out data/dpo.jsonl --min-score 70
```

The `review list` output shows proposal IDs. To test the approval/apply path, approve a listed proposal by full ID or unique prefix, then run `apply`:

```bash
python -m skillloop.cli --path . review approve <proposal-id-or-prefix>
python -m skillloop.cli --path . apply
```

You can also use the console script after installation:

```bash
skillloop --path . init
skillloop --path . ingest generic examples/traces/simple_trace.jsonl
```

## CLI overview

```text
skillloop --path <project-root> init
skillloop --path <project-root> ingest generic <jsonl-path>
skillloop --path <project-root> ingest hermes <json-path>
skillloop --path <project-root> ingest hermes-db --latest [--db-path ~/.hermes/state.db]
skillloop --path <project-root> ingest hermes-db --session-id <id> [--db-path ~/.hermes/state.db]
skillloop --path <project-root> traces list
skillloop --path <project-root> traces show <trace-id|latest>
skillloop --path <project-root> eval <trace-id|latest>
skillloop --path <project-root> distill <trace-id|latest>
skillloop --path <project-root> review list [--verbose]
skillloop --path <project-root> review approve <proposal-id-prefix>
skillloop --path <project-root> review reject <proposal-id-prefix>
skillloop --path <project-root> apply
skillloop --path <project-root> export sft --out <path> [--min-score N]
skillloop --path <project-root> export dpo --out <path> [--min-score N]
```

## Clean export boundary

SkillLoop writes only under the selected project root by default:

- local state: `.skillloop/skillloop.db`
- approved memory exports: `.skillloop/approved/memory/*.md`
- approved skill exports: `.skillloop/approved/skill/*.md`
- training data exports: user-selected paths such as `data/sft.jsonl`

This is intentional. The first version is a clean export layer, not a global self-mutating runtime.

## Repository layout

```text
skillloop/
  adapters/      Trace ingestion adapters
  apply/         Review-approved filesystem exports
  distill/       Memory and skill proposal generation
  eval/          Trace scoring heuristics
  export/        SFT and DPO dataset exporters
  review/        Proposal review queue helpers
  cli.py         Command-line interface
  schema.py      Normalized trace/eval/proposal dataclasses
  store.py       SQLite persistence layer
examples/
  traces/        Sample input traces
tests/           Pytest coverage for the MVP
docs/            Architecture and usage documentation
```

## Safety model

SkillLoop is review-first:

- Ingested traces are stored locally
- Distillation creates proposals, not global mutations
- Human approval is required before `apply`
- Approved exports stay inside `.skillloop/approved/`
- `.env`, `.env.*`, generated datasets, and local state are gitignored

See `docs/safety.md` for details.

## Development checks

```bash
python -m pytest tests/ -q
python -m compileall skillloop tests -q
python -m pip wheel . --no-deps -w /tmp/skillloop-wheel-check
```

Expected MVP result: all tests pass and the sample workflow exports at least one SFT record.

## Proof-of-work status

This repository is an initial proof-of-work for the SkillLoop architecture. It already demonstrates the core loop:

trace ingestion → evaluation → memory/skill proposals → human review → safe local apply → fine-tuning data export

See:

- `docs/architecture.md` for system design
- `docs/cli.md` for commands
- `docs/safety.md` for safety boundaries
- `docs/trace-schema.md` for data format

## License

Apache-2.0. See `LICENSE`.
