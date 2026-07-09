# Changelog

## 0.2.0

- Installable via `pipx install git+https://github.com/lamenting-hawthorn/skillloop` (GitHub) and wheel.
- Added `python -m skillloop` as a stable module entry point.
- Added `skillloop --version` and `skillloop doctor` diagnostics commands.
- SQLite store upgraded to schema v2 with automatic migration, new indexes, bulk insert/query paths, and a busy-timeout.
- Added Python 3.13 to CI matrix and a clean-wheel build check.
- Rewrote public documentation to reflect the sidecar architecture, Hermes UX, loop primitives, dataset manifests, training config generation, and safety boundaries.
- Changed project license posture from proprietary/all-rights-reserved to Apache-2.0.

## 0.1.0 - MVP

Initial local prototype.

### Added

- Python package and CLI
- Generic JSONL trace adapter
- Hermes-like trace adapter
- Hermes `state.db` read-only ingestion
- Normalized trace schema with runtime/adapter metadata
- Span-ready tool-call schema
- SQLite local store
- Raw trace preservation and content hashes
- Deterministic evaluation heuristics
- Evaluator registry and replay benchmarks
- Memory and skill proposal distillation
- Review queue with approve/reject/apply flow
- Project-local apply/export boundary
- SFT and conservative DPO JSONL exporters
- Dataset manifests with split/count/token/provenance summaries
- Training config generation for TRL, Unsloth, and Axolotl without running training
- Local loop schedule/tick primitives
- Policy-driven controller ticks
- `setup --connect hermes --start`
- `status`
- `controller run/history/show`
- Sample trace and pytest coverage
- Documentation for architecture, CLI usage, safety, schema, and contributing
