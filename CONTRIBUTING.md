# Contributing to SkillLoop

SkillLoop is currently a proprietary, all-rights-reserved project. Contributions are welcome only when explicitly requested or approved by the maintainer.

By opening a pull request, submitting a patch, or otherwise contributing material to this repository, you represent that you have the right to submit the contribution and you grant the maintainer a perpetual, worldwide, royalty-free right to use, modify, reproduce, distribute, sublicense, and incorporate that contribution into SkillLoop under the project's current or future licensing terms. If you do not agree to this, do not submit a contribution.

## Project position

SkillLoop is a local learning governor for agent runtimes. Hermes is the source-of-truth runtime substrate; SkillLoop reads completed traces and produces governed learning artifacts. It must not duplicate or silently mutate Hermes runtime systems.

Core constraints:

- local-first by default
- no mandatory cloud dependency
- read-only Hermes `state.db` ingestion
- no global Hermes mutation in v1
- no credential storage
- review-before-apply behavior
- generated local state remains gitignored
- no auto-training or auto-promotion
- provenance on evaluations, proposals, datasets, and training artifacts

## Development setup

```bash
python -m pip install -e '.[dev]'
```

SkillLoop requires Python 3.11+.

## Required checks

Run these before proposing a change:

```bash
python -m pytest -q
python -m compileall skillloop tests -q
git diff --check
```

Optional package check:

```bash
python -m pip wheel . --no-deps -w /tmp/skillloop-wheel-check
```

## Contribution guidelines

### Keep changes focused

Prefer small, reviewable changes. A good PR changes one layer at a time: adapter, evaluator, store, CLI, docs, dataset export, etc.

### Update documentation with behavior changes

If a CLI command, schema, safety boundary, policy field, dataset format, or lifecycle behavior changes, update the relevant docs in the same change:

- `README.md`
- `docs/cli.md`
- `docs/architecture.md`
- `docs/safety.md`
- `docs/trace-schema.md`
- `CHANGELOG.md`

### Never commit private/generated state

Do not commit:

- `.skillloop/`
- `.env` or `.env.*`
- generated datasets under `data/*.jsonl`
- credentials, API keys, tokens, cookies, phone numbers, or private user data
- local handoff/private planning docs unless the maintainer explicitly asks

### Adding adapters

New adapters should:

- normalize runtime-specific traces into `AgentTrace` early
- preserve adapter/runtime metadata
- preserve raw trace references and hashes where possible
- tolerate unknown fields
- avoid silently dropping corrupted data
- redact obvious secrets before storage/export
- stay read-only against source runtimes

### Adding evaluators

Evaluators should:

- be deterministic unless explicitly marked as LLM-based
- record evaluator name/version
- emit structured evidence, not just scores
- prefer tool outputs, exit codes, user feedback, and artifact checks over assistant claims
- remain benchmarkable through `skillloop benchmark`

Do not add LLM evaluators until cost tracking and budget policy exist.

### Adding distillers

Distillers should create proposals, not mutations. Proposals need:

- trace provenance
- producer provenance
- clear reason text
- reviewable content
- safety notes when relevant

Avoid saving one-off task state, credentials, or stale facts as memories/skills.

### Adding dataset or training features

Dataset/training work must remain conservative:

- validate JSONL shape
- preserve source trace IDs
- include manifests and token/count estimates
- keep DPO export explicit-preference only unless a new reviewed preference-generation gate exists
- generate training configs only unless a separate approved training runner is implemented
- never store hub tokens or credentials in SkillLoop state

## Pull request checklist

- [ ] Change is scoped and reviewable
- [ ] Tests pass
- [ ] Compile check passes
- [ ] `git diff --check` passes
- [ ] README/docs updated for behavior changes
- [ ] No secrets, private traces, local `.skillloop/` state, or generated datasets committed
- [ ] Safety boundaries are preserved
- [ ] Any new proposal/evaluation/export artifact includes provenance
- [ ] Any training-related change remains approval-gated and does not auto-run training

## License reminder

This project is proprietary and all rights are reserved. Do not reuse, copy, distribute, or incorporate any part of SkillLoop without written permission from the copyright holder.
