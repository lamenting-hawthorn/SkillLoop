# Loop Engineering Skills for Hermes

These are Hermes Agent skills that implement the loop engineering framework
described in `docs/analysis/loop-engineering-analysis.md`.

## What's here

| Skill | Purpose |
|-------|---------|
| `pre-loop-checklist` | Gate before creating any cron job: 4-condition test + 30-second checklist |
| `goal-loop` | The /goal pattern: cron jobs that run until an objective condition is met |
| `cron-job-workflows` | State management, Ralph Wiggum detection, watchdog patterns |

## How to install

Copy to your Hermes skills directory:

```bash
# Install all three
cp -r references/hermes-skills/pre-loop-checklist ~/.hermes/skills/system/
cp -r references/hermes-skills/goal-loop ~/.hermes/skills/system/
cp -r references/hermes-skills/cron-job-workflows ~/.hermes/skills/system/

# Verify
hermes skills list | grep -E "pre-loop|goal-loop|cron-job"
```

Or install individually via Hermes:

```bash
hermes skills install /path/to/skillloop/references/hermes-skills/pre-loop-checklist/SKILL.md
```

## Skill relationship

```
pre-loop-checklist (gate: should I build a loop?)
       │
       ├──→ cron-job-workflows (how to build and maintain loops)
       │
       └──→ goal-loop (the /goal pattern: run until condition met)
```

## Origin

Derived from the [0xCodez loop engineering framework](https://movez.substack.com/p/loop-engineering-the-14-step-roadmap)
(June 2026), Anthropic's evaluator-optimizer pattern, and Addy Osmani's loop
engineering essay. Full analysis: `docs/analysis/loop-engineering-analysis.md`.
