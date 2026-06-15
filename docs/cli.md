# CLI Reference

All commands accept a global `--path` argument. The path selects the project root where SkillLoop stores local state.

```bash
python -m skillloop.cli --path . <command>
```

After installation, the `skillloop` console script is equivalent:

```bash
skillloop --path . <command>
```

## `init`

Initializes local SkillLoop state.

```bash
skillloop --path . init
```

Creates:

```text
.skillloop/skillloop.db
```

## `setup`

Configures SkillLoop as a local sidecar for Hermes by writing `.skillloop/policy.json` with `hermes-db` ingestion. With `--start`, it immediately runs one controller tick.

```bash
skillloop --path . setup --connect hermes --start
skillloop --path . setup --connect hermes --db-path ~/.hermes/state.db --max-sessions 20 --auto-export
```

This is read-only against Hermes `state.db`; SkillLoop writes only under the selected `--path` root.

## `status`

Shows configured policy path, trace/evaluation/proposal counts, and the latest controller run.

```bash
skillloop --path . status
skillloop --path . status --json
```

## `ingest generic`

Ingests a generic JSONL trace.

```bash
skillloop --path . ingest generic examples/traces/simple_trace.jsonl
```

Each line should contain a message-like object. The adapter tolerates unknown fields.

## `ingest hermes`

Ingests Hermes-like JSON exports.

```bash
skillloop --path . ingest hermes path/to/export.json
```

The adapter normalizes known message and tool-call fields into the internal schema.

## `ingest hermes-db`

Ingests directly from a Hermes `state.db` file using SQLite read-only mode. This reads session messages but does not mutate Hermes state.

```bash
skillloop --path . ingest hermes-db --latest
skillloop --path . ingest hermes-db --session-id <session-id>
skillloop --path . ingest hermes-db --db-path ~/.hermes/state.db --latest
```

By default, `--db-path` is `~/.hermes/state.db`.

## `traces list`

Lists stored traces.

```bash
skillloop --path . traces list
```

## `traces show`

Shows a specific trace or the latest trace.

```bash
skillloop --path . traces show latest
skillloop --path . traces show <trace-id>
```

## `eval`

Evaluates a trace and stores an `Evaluation` record.

```bash
skillloop --path . eval latest
skillloop --path . eval <trace-id>
skillloop --path . eval latest --evaluator rubric
```

## `distill`

Creates memory and skill proposals from a trace.

```bash
skillloop --path . distill latest
skillloop --path . distill <trace-id>
```

## `review list`

Lists pending proposals.

```bash
skillloop --path . review list
skillloop --path . review list --verbose
```

## `review approve`

Approves a proposal by full ID or unique prefix.

```bash
skillloop --path . review approve <proposal-id-or-prefix>
```

## `review reject`

Rejects a proposal by full ID or unique prefix.

```bash
skillloop --path . review reject <proposal-id-or-prefix>
```

## `apply`

Writes approved proposals into project-local approved export files.

```bash
skillloop --path . apply
```

Writes to:

```text
.skillloop/approved/memory/*.md
.skillloop/approved/skill/*.md
```

## `export sft`

Exports supervised fine-tuning records.

```bash
skillloop --path . export sft --out data/sft.jsonl
skillloop --path . export sft --out data/sft.jsonl --min-score 70
skillloop --path . export sft --out data/sft.jsonl --splits train=0.8,validation=0.1,test=0.1
skillloop --path . export sft --out data/sft.jsonl --manifest-out data/manifest.json
```

Use `--min-score N` to export only traces with a stored evaluation score greater than or equal to `N`. Traces without evaluations are skipped when this gate is active.

Exports always write a dataset manifest. By default the manifest path is `<out>.manifest.json`; pass `--manifest-out` to choose a path. The manifest includes output file paths, export metadata, split-level record/token stats, trace/evaluation/proposal provenance summaries, and evaluator counts.

Use `--splits` to write deterministic split files. For example `--splits train=0.8,validation=0.1,test=0.1` writes `data/sft.train.jsonl`, `data/sft.validation.jsonl`, and `data/sft.test.jsonl`.

Record shape:

```json
{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}], "metadata": {"trace_id": "...", "evaluation_id": "..."}}
```

## `export dpo`

Exports preference records when chosen/rejected data is available.

```bash
skillloop --path . export dpo --out data/dpo.jsonl
skillloop --path . export dpo --out data/dpo.jsonl --min-score 70
skillloop --path . export dpo --out data/dpo.jsonl --splits train=0.9,test=0.1
```

Record shape:

```json
{"prompt": "...", "chosen": "...", "rejected": "...", "metadata": {"trace_id": "...", "evaluation_id": "..."}}
```

## `benchmark`

Replays stored traces through evaluator versions and writes a report that compares scores, deltas, tags, and evidence counts. Use this before training to prove an evaluator change is at least non-regressing on a small trace suite.

```bash
skillloop --path . benchmark
skillloop --path . benchmark --baseline rubric_legacy --candidates rubric --out data/benchmark.json
skillloop --path . benchmark --trace-id latest --out data/latest-benchmark.json
```

Report shape:

```json
{"baseline":"rubric_legacy","candidates":["rubric"],"summary":{"traces":1,"average_delta":{"rubric":0}},"cases":[{"trace_id":"...","scores":{"rubric_legacy":70,"rubric":75}}]}
```

## `training-config`

Generates training configuration artifacts for Unsloth, TRL, or Axolotl from a dataset manifest. This command does not run training. Generated files include explicit safety metadata showing `training_auto_run: false` / `training_auto_run=false` equivalent fields.

```bash
skillloop --path . training-config trl --dataset-manifest data/sft.jsonl.manifest.json --base-model NousResearch/Meta-Llama-3.1-8B --output-dir runs/trl-sft --config-dir configs/trl
skillloop --path . training-config unsloth --dataset-manifest data/sft.jsonl.manifest.json --base-model unsloth/llama-3-8b --output-dir runs/unsloth-sft --config-dir configs/unsloth
skillloop --path . training-config axolotl --dataset-manifest data/sft.jsonl.manifest.json --base-model NousResearch/Meta-Llama-3.1-8B --output-dir runs/axolotl-sft --config-dir configs/axolotl
```

Generated files:

```text
configs/trl/trl_sft_config.json
configs/unsloth/unsloth_config.json
configs/unsloth/unsloth_sft_skeleton.py
configs/axolotl/axolotl_config.yml
```

## `controller run/history/show`

Runs the autonomous controller once using `.skillloop/policy.json` if present, and inspects prior run reports stored in SQLite.

```bash
skillloop --path . controller run
skillloop --path . controller history
skillloop --path . controller history --limit 5
skillloop --path . controller show <run-id-or-prefix>
```

Controller run reports are also mirrored as JSON under `.skillloop/controller_runs/` for easy inspection.

## Full smoke test

```bash
tmp=$(mktemp -d)
cp -R examples "$tmp/"
python -m skillloop.cli --path "$tmp" init
python -m skillloop.cli --path "$tmp" ingest generic "$tmp/examples/traces/simple_trace.jsonl"
python -m skillloop.cli --path "$tmp" traces list
python -m skillloop.cli --path "$tmp" eval latest
python -m skillloop.cli --path "$tmp" distill latest
python -m skillloop.cli --path "$tmp" review list --verbose
python -m skillloop.cli --path "$tmp" export sft --out "$tmp/sft.jsonl" --min-score 70
python -m skillloop.cli --path "$tmp" benchmark --out "$tmp/benchmark.json"
test -s "$tmp/sft.jsonl"
test -s "$tmp/sft.jsonl.manifest.json"
test -s "$tmp/benchmark.json"
echo "$tmp"
```
