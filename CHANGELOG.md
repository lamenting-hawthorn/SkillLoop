# Changelog

## Unreleased

### Changed

- Rewrote public documentation to reflect the current SkillLoop sidecar architecture, Hermes setup/status/controller UX, loop primitives, dataset manifests, training config generation, and safety boundaries.
- Changed project license posture from Apache-2.0 to proprietary/all-rights-reserved.

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
