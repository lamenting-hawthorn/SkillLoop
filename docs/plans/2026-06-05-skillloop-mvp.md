# SkillLoop MVP Implementation Plan

> For Hermes: Keep all files inside `/Users/raghav/skillloop`. Do not modify existing Hermes architecture, config, skills, memories, or any other project.

Goal: Build a standalone self-improving agent harness layer that can ingest agent traces, evaluate them, propose memory/skill updates, review/apply approved changes, and export fine-tuning-ready datasets.

Architecture: SkillLoop is a separate Python CLI package. Hermes is the first adapter, but the core uses a generic normalized trace schema so Pi/Codex/Claude Code/OpenCode adapters can be added later. V1 does not run fine-tuning; it exports curated SFT/DPO JSONL.

Tech Stack: Python 3.11+, stdlib-first, SQLite, JSONL, pytest, argparse. No mandatory cloud services.

---

## Milestone 1: Project scaffold

Objective: Create an isolated installable Python package with a CLI and tests.

Files:
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `skillloop/__init__.py`
- Create: `skillloop/cli.py`
- Create: `tests/test_cli.py`

Verification:
- `python -m pytest tests/ -q`
- `python -m skillloop.cli --help`

## Milestone 2: Normalized trace schema

Objective: Define stable dataclasses for agent traces, messages, tool calls, evaluations, and proposals.

Files:
- Create: `skillloop/schema.py`
- Test: `tests/test_schema.py`

Behavior:
- serialize/deserialize traces to dict/JSON
- validate required fields
- preserve source metadata

Verification:
- `python -m pytest tests/test_schema.py -q`

## Milestone 3: SQLite store

Objective: Persist traces, evaluations, and proposals locally.

Files:
- Create: `skillloop/store.py`
- Test: `tests/test_store.py`

Behavior:
- initialize `.skillloop/skillloop.db`
- save/list/get traces
- save/list proposals
- no writes outside requested project directory

Verification:
- `python -m pytest tests/test_store.py -q`

## Milestone 4: Trace adapters

Objective: Ingest generic JSONL and Hermes-style exported/session JSON traces.

Files:
- Create: `skillloop/adapters/generic_jsonl.py`
- Create: `skillloop/adapters/hermes.py`
- Test: `tests/test_adapters.py`
- Create: `examples/traces/simple_trace.jsonl`

Behavior:
- parse simple JSONL messages
- normalize Hermes-like message/tool records when present
- tolerate unknown fields

Verification:
- `python -m pytest tests/test_adapters.py -q`

## Milestone 5: Evaluation engine

Objective: Score traces with deterministic heuristics first, leaving LLM judges pluggable later.

Files:
- Create: `skillloop/eval/rubric.py`
- Test: `tests/test_eval.py`

Behavior:
- produce score 0-100
- tag missing final answer, errors, tool failures, user correction, success signals
- output actionable notes

Verification:
- `python -m pytest tests/test_eval.py -q`

## Milestone 6: Distillation engine

Objective: Propose memory and skill candidates from traces.

Files:
- Create: `skillloop/distill/memory.py`
- Create: `skillloop/distill/skills.py`
- Test: `tests/test_distill.py`

Behavior:
- memory proposals only for durable facts/preferences/conventions
- skill proposals include trigger, steps, pitfalls, verification
- avoid credentials/secrets

Verification:
- `python -m pytest tests/test_distill.py -q`

## Milestone 7: Review and apply

Objective: Save proposals for human approval and apply only when explicitly requested.

Files:
- Create: `skillloop/review/queue.py`
- Create: `skillloop/apply/filesystem.py`
- Test: `tests/test_review_apply.py`

Behavior:
- default dry-run
- approved proposals written under project `.skillloop/approved/`
- Hermes global apply is not implemented in v1 to avoid touching existing architecture

Verification:
- `python -m pytest tests/test_review_apply.py -q`

## Milestone 8: Dataset export

Objective: Export fine-tuning-ready SFT/DPO JSONL from curated traces.

Files:
- Create: `skillloop/export/sft.py`
- Create: `skillloop/export/dpo.py`
- Test: `tests/test_export.py`

Behavior:
- SFT: `{messages: [...]}` format
- DPO: `{prompt, chosen, rejected}` when feedback exists
- skip low-quality/incomplete traces by default

Verification:
- `python -m pytest tests/test_export.py -q`

## Initial CLI Commands

- `skillloop --path . init`
- `skillloop --path . ingest generic examples/traces/simple_trace.jsonl`
- `skillloop --path . traces list`
- `skillloop --path . eval <trace_id>`
- `skillloop --path . distill <trace_id>`
- `skillloop --path . review list`
- `skillloop --path . export sft --out data/sft.jsonl`

## MVP Acceptance Criteria

- All tests pass.
- Running the sample trace through ingest → eval → distill → review → export works.
- No command writes outside `/Users/raghav/skillloop` unless explicitly passed another path.
- No credentials are read or stored.
- Fine-tuning is positioned as dataset export only, not automatic self-training.
