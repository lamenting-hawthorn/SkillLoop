# CLI Reference

All commands accept the global `--path` argument. The path selects the project root where SkillLoop stores local state.

```bash
skillloop --path . <command>
```

Equivalent module form:

```bash
python -m skillloop --path . <command>
```

## Local Deployment

SkillLoop deploys as a project-local sidecar. The current one-time setup path is:

```bash
pipx install git+https://github.com/lamenting-hawthorn/skillloop.git
skillloop --path /path/to/project setup --connect hermes --start --auto-export
```

That creates `.skillloop/policy.json`, reads Hermes sessions from
`~/.hermes/state.db`, runs one controller tick, stores local state in
`.skillloop/`, and writes a dataset manifest when auto-export is enabled.

`setup --start` is a one-shot controller run. It does not install, bootstrap, or
start a background service.

For recurring controller ticks on macOS:

```bash
skillloop --path /path/to/project service install --kind launchd --interval-seconds 3600
skillloop --path /path/to/project service status
```

`service install` writes a launchd plist and `.skillloop/service.json`, then
prints the exact `launchctl` command. It does not silently load the service.

Current deployment scope:

- macOS launchd plist generation is implemented.
- Linux systemd/cron generation is not implemented yet.
- No cloud service is required.
- SkillLoop does not mutate Hermes memory, skills, config, cron jobs, tools, or
  model state.
- GitHub, wheel, and editable installs expose the same CLI.

## `init`

Initializes local SkillLoop state.

```bash
skillloop --path . init
```

Creates:

```text
.skillloop/skillloop.db
```

## `doctor`

Runs read-only package, Python, project, SQLite, policy, output-boundary, and
connector checks. Use `--json` for automation; failed required checks return a
non-zero exit code.

## `setup`

Configures SkillLoop as a local sidecar for Hermes by writing `.skillloop/policy.json` with read-only `hermes-db` ingestion. With `--start`, it immediately runs one controller tick.

```bash
skillloop --path . setup --connect hermes --start
skillloop --path . setup --connect hermes --db-path ~/.hermes/state.db --max-sessions 20 --min-score 70 --auto-export --dataset-out data/sft.jsonl --start
```

Important behavior:

- validates that `--db-path` exists
- validates positive `--max-sessions`
- validates `--min-score` in `0..100`
- writes a conservative `.skillloop/policy.json`
- reads Hermes `state.db` only; it does not mutate Hermes
- `--auto-export` enables controller-managed SFT export by writing `dataset.auto_update: true`
- controller-managed export includes only traces whose latest evaluation passes the configured evaluation condition and dataset score gate

## `status`

Shows configured policy path, trace/evaluation/proposal counts, dataset stats, and the latest controller run.

```bash
skillloop --path . status
skillloop --path . status --json
```

If a dataset manifest exists but cannot be decoded, status reports a manifest error instead of throwing a raw traceback.

## `ingest generic`

Ingests a generic JSONL trace.

```bash
skillloop --path . ingest generic examples/traces/simple_trace.jsonl
```

Each line should contain a message-like object. Unknown fields are tolerated. Common secret patterns are redacted.

## `ingest hermes`

Ingests Hermes-like JSON exports.

```bash
skillloop --path . ingest hermes path/to/export.json
```

The adapter normalizes known message and tool-call fields into the internal schema.

## `ingest hermes-db`

Ingests directly from a Hermes `state.db` file using read-only SQLite access.

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
skillloop --path . traces show <trace-id-or-prefix>
```

## `eval`

Evaluates a trace and stores an `Evaluation` record.

```bash
skillloop --path . eval latest
skillloop --path . eval <trace-id-or-prefix>
skillloop --path . eval latest --evaluator rubric
```

Current evaluators are deterministic and local. Use `benchmark` to compare evaluator behavior across stored traces.

## `distill`

Creates memory and skill proposals from a trace.

```bash
skillloop --path . distill latest
skillloop --path . distill <trace-id-or-prefix>
```

Distillation writes proposals to the review queue. It does not mutate Hermes or global agent state.

## `review list`

Lists proposals.

```bash
skillloop --path . review list
skillloop --path . review list --verbose
skillloop --path . review list --all
skillloop --path . review list --status approved
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
skillloop --path . apply --out-dir .skillloop/approved
```

Writes to:

```text
.skillloop/approved/memory/*.md
.skillloop/approved/skill/*.md
```

This is an export boundary, not live runtime mutation.

## `export sft`

Exports supervised fine-tuning records.

```bash
skillloop --path . export sft --out data/sft.jsonl
skillloop --path . export sft --out data/sft.jsonl --min-score 70
skillloop --path . export sft --out data/sft.jsonl --splits train=0.8,validation=0.1,test=0.1
skillloop --path . export sft --out data/sft.jsonl --manifest-out data/manifest.json
```

Use `--min-score N` to export only traces with at least one stored evaluation score greater than or equal to `N`. Traces without evaluations are skipped when this gate is active.

Exports always write a dataset manifest. By default the manifest path is `<out>.manifest.json`; pass `--manifest-out` to choose a path.

The manifest includes output file paths, export metadata, split-level record/token stats, trace/evaluation/proposal provenance summaries, and evaluator counts.

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

DPO export is conservative in v1 and only exports explicit preference pairs already present in trace metadata.

Record shape:

```json
{"prompt": "...", "chosen": "...", "rejected": "...", "metadata": {"trace_id": "...", "evaluation_id": "..."}}
```

## `benchmark`

Replays stored traces through evaluator versions and writes a report comparing scores, deltas, tags, and evidence counts.

```bash
skillloop --path . benchmark
skillloop --path . benchmark --baseline rubric_legacy --candidates rubric --out data/benchmark.json
skillloop --path . benchmark --trace-id latest --out data/latest-benchmark.json
```

Use this before trusting an evaluator change for dataset export or training data readiness.

Report shape:

```json
{"baseline":"rubric_legacy","candidates":["rubric"],"summary":{"traces":1,"average_delta":{"rubric":0}},"cases":[{"trace_id":"...","scores":{"rubric_legacy":70,"rubric":75}}]}
```

## `training-config`

Generates training configuration artifacts for Unsloth, TRL, or Axolotl from a dataset manifest. This command does not run training.

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

Generated configs include explicit no-auto-run safety metadata.

## `loop run`

Runs one local outer-loop evaluation/distillation pass.

```bash
skillloop --path . loop run
skillloop --path . loop run --min-score 80
skillloop --path . loop run --require-tag success_signal --forbid-tag tool_failure
skillloop --path . loop run --condition '{"score_gte":80,"forbidden_tags":["tool_failure"]}'
```

## `loop schedule/status/tick`

Writes and executes a project-local loop schedule. This is a local scheduling primitive, not an installed OS background service.

```bash
skillloop --path . loop schedule --interval daily --min-score 70
skillloop --path . loop status
skillloop --path . loop tick
skillloop --path . loop tick --force
```

Supported intervals:

- `hourly`
- `daily`
- `weekly`

## `controller run/history/show`

Runs the autonomous controller once using `.skillloop/policy.json` if present, and inspects prior run reports stored in SQLite.

```bash
skillloop --path . controller run
skillloop --path . controller history
skillloop --path . controller history --limit 5
skillloop --path . controller show <run-id-or-prefix>
```

Controller run reports are also mirrored as JSON under `.skillloop/controller_runs/` for easy inspection. If policy has `dataset.auto_update: true` (or legacy `dataset.enabled: true`), controller ticks update the configured dataset using only traces whose latest evaluation passes the evaluation condition and dataset score gate.

## `service install/status/uninstall`

Installs, inspects, and removes the project-local background controller service metadata. On macOS, `service install` writes a launchd plist that runs `skillloop --path <project-root> controller run` on an interval. It prints the exact `launchctl bootstrap` / `bootout` commands instead of silently loading the service.

```bash
skillloop --path . service install --kind launchd --interval-seconds 3600
skillloop --path . service status
skillloop --path . service status --json
skillloop --path . service uninstall
```

Generated files:

```text
~/Library/LaunchAgents/com.skillloop.controller.<hash>.plist
.skillloop/service.json
.skillloop/service.out.log
.skillloop/service.err.log
```

Use `--launch-agents-dir` to write the plist somewhere else for tests or dry-run inspection.

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

The final `echo` prints the temporary directory so the artifacts can be inspected manually.
