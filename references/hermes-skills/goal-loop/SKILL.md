---
name: goal-loop
description: "The /goal pattern: cron jobs that run until an objective condition is met, checked by an independent model (maker/checker split). Source: loop engineering framework by 0xCodez / Anthropic evaluator-optimizer pattern."
version: 1.0.0
author: Hermes Agent
license: Apache-2.0
metadata:
  hermes:
    tags: [loop-engineering, cron, goal, automation, maker-checker, evaluator-optimizer]
    related_skills: [pre-loop-checklist, cron-job-workflows]
    source: "Adapted from Loop engineering: the 14-step roadmap from prompter to loop designer by 0xCodez (movez.substack.com)"
---

# Goal Loop — The /goal Pattern

The `/goal` primitive: a cron job that runs on a cadence until an **objective
condition** is met, verified by an **independent checker model** — not the agent
that writes the code. This is the maker-vs-checker split applied to the stop
condition itself.

## When to Use

- After passing the `pre-loop-checklist` (4-condition test + 30-second check)
- When you have a clear, machine-checkable goal condition
- When the work is iterative (agent tries, fails, learns, retries)
- When verification can be fully automated

Do NOT use for:
- One-shot tasks (use a single `delegate_task`)
- Vague goals ("make it better")
- Work that can't be verified by a test/build/linter
- Anything where "done" is a judgment call

## The Pattern (4 Parts)

```
                     ┌──────────────────────┐
                     │   Cron job fires on   │
                     │   cadence (e.g. 30m)  │
                     └──────────┬───────────┘
                                │
                     ┌──────────▼───────────┐
                     │  Read STATE.md        │
                     │  (resume, don't       │
                     │   restart from zero)  │
                     └──────────┬───────────┘
                                │
                     ┌──────────▼───────────┐
                     │  CHECKER subagent     │
                     │  (DIFFERENT model)    │
                     │  Evaluate: is goal    │
                     │  condition met?       │
                     └──────────┬───────────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
                    ▼                       ▼
              ┌──────────┐           ┌──────────┐
              │  GOAL    │           │  GOAL    │
              │  MET ✓   │           │  NOT MET │
              └────┬─────┘           └────┬─────┘
                   │                      │
                   ▼                      ▼
              ┌──────────┐           ┌──────────┐
              │  Report  │           │  WORKER   │
              │  success │           │  subagent │
              │  Update  │           │  (does    │
              │  STATE   │           │   the     │
              │  Option: │           │   work)   │
              │  self-   │           └────┬─────┘
              │  cancel  │                │
              └──────────┘                ▼
                                   ┌──────────┐
                                   │  Update  │
                                   │  STATE   │
                                   │  Report  │
                                   │  progress│
                                   │  (loop   │
                                   │   again  │
                                   │   next   │
                                   │   tick)  │
                                   └──────────┘
```

## Prerequisites

Before creating a goal loop, ensure:

1. **A hard gate exists** — test suite, linter, type checker, or build that can
   OBJECTIVELY fail bad output. No gate = Ralph Wiggum loop.
2. **A reproduction environment** — the worker can run the code it changes.
3. **STATE.md template ready** — where the loop records progress across runs.
   See cron-job-workflows skill for the template.
4. **A different model for the checker** — the model that verifies must NOT be
   the same as the model that writes. Configure via `delegation.model` in
   config.yaml. Self-preferential bias is real: the maker grades its own
   homework and it's always "A+."

## The Goal Condition

Must be **objective and machine-verifiable**. The checker evaluates it, not the
worker.

| Good goal conditions | Bad goal conditions |
|---|---|
| "All tests in test/auth pass" | "The code looks good" |
| "Lint returns zero errors" | "The auth module is done" |
| "Build succeeds on main branch" | "Everything is fixed" |
| "Type check passes with zero errors" | "The performance is acceptable" |
| "CI is green on PR #42" | "It's better than before" |

## Setup: Creating a Goal Loop

### Step 1: Pass the pre-loop-checklist

Load `pre-loop-checklist` skill and run the 4-condition test + 30-second
checklist against the task. If it doesn't pass, do NOT build a goal loop.

### Step 2: Initialize STATE.md

Create a STATE.md in the project root (or .hermes/ directory) using the
template from cron-job-workflows skill. After creating the cron job, persist
the exact returned `job_id` in STATE.md so the loop can self-cancel safely.
The first run reads this to resume.

### Step 3: Create the cron job

Use the prompt template below. Replace the bracketed values.

### Step 4: Monitor the first 3 runs

Watch the first 3-5 runs manually. Verify:
- The checker is actually checking (not just rubber-stamping)
- The worker is actually working (not looping on the same thing)
- STATE.md is being updated
- The gate is catching bad output

## Prompt Template

Copy this template, fill in the brackets, and pass as the `prompt` to
`cronjob(action='create', ...)`.

```
You are a /goal loop runner. Your job is to achieve a specific,
machine-checkable goal. You run on a cadence and check progress each
tick. Do NOT do the work yourself — delegate everything.

## Goal condition
{GOAL_CONDITION — e.g., "All tests in test/auth pass and lint is clean"}

## Work to do when goal is not met
{WORK_DESCRIPTION — e.g., "Scan src/auth for failing tests, draft fixes
on branch claude/auth-fixes, open draft PR when ready"}

## State file
Read {PATH_TO_STATE_MD} at the start of every run. Update it at the end.
Use the standard STATE.md format from cron-job-workflows skill.

## Each tick (every run):

### 1. Read state
Read {PATH_TO_STATE_MD} to understand current progress and what happened
last run.

### 2. Check the goal (CHECKER — use a DIFFERENT model)
Dispatch a checker subagent via delegate_task:
- goal: "Verify if goal condition is met: {GOAL_CONDITION}"
- The checker must run the actual verification (tests, lint, build) — NOT
  just read files. It must produce an objective PASS or FAIL.
- Use toolsets: ['terminal', 'file']
- This subagent must use a DIFFERENT model from the worker. Set up
  delegation config accordingly.

### 3. If goal is MET:
- Write final status to STATE.md under "## Stop conditions met"
- Final response: report success with specific evidence (test output,
  commit hash, etc.)
- IMPORTANT: The job's STATE.md must contain the exact `job_id` returned
  when the loop was created. After reporting success, read that stored ID
  and call cronjob(action='remove', job_id=STORED_JOB_ID) to self-cancel.
- Do NOT continue running after goal is met.

### 4. If goal is NOT met:
- Dispatch a worker subagent via delegate_task:
  - goal: "Make progress toward: {GOAL_CONDITION}"
  - context: Include the checker's findings, current state from STATE.md,
    and the work description: {WORK_DESCRIPTION}
  - toolsets: ['terminal', 'file']
  - The worker changes code, creates branches, runs tests

- After worker completes, verify:
  a. Was anything actually shipped (not just "analyzed")?
  b. Did the worker's changes get past the gate (tests pass, lint clean)?
  c. If nothing changed or gate failed → record in STATE.md and escalate

- Update STATE.md:
  - "## Last run" — timestamp + summary
  - "## In progress" — what's being worked on
  - "## Completed today" — what finished
  - "## Escalated to humans" — what needs a human
  - Update "## Efficiency" counters

- Final response: report progress (what was done, what remains, when next
  tick fires)

## Hard stops
- Token budget: {MAX_TOKENS_PER_RUN or "stop after 3 worker attempts per tick"}
- Time limit: tick must complete within {TIME_LIMIT}
- If approaching limits, report partial progress and defer to next tick

## Never do
- Do the work yourself (always delegate to worker subagent)
- Let the checker and worker use the same model (self-preferential bias)
- Skip the STATE.md update
- Continue running after goal is met (self-cancel)
- Accept "done enough" without the gate passing
- Touch {RESTRICTED_PATHS — e.g., "src/payments/, src/auth/, production configs"}
```

## Example: CI Triage Goal Loop

```python
job = cronjob(
    action='create',
    name='auth-quality-goal-loop',
    schedule='30m',
    deliver='origin',
    prompt="""You are a /goal loop runner.

## Goal condition
All tests in test/auth/ pass AND lint returns zero errors on src/auth/

## Work to do
Scan CI failures in test/auth/, classify root causes, draft fixes on
branches under claude/auth-fixes/, run tests locally, open draft PRs when
fixes pass locally.

## State file
Read STATE.md at project root. Update it at the end of every run.

[Full template follows with checked values...]
""",
    workdir='<your-project-path>',
    skills=['pre-loop-checklist', 'cron-job-workflows'],
    enabled_toolsets=['terminal', 'file', 'delegation', 'cronjob'],
)
# Record job['job_id'] in STATE.md before the first tick runs.
```

## Self-Cancellation

When the goal is met, the cron agent calls:

```python
# Read the exact job_id persisted in STATE.md when the loop was created.
cronjob(action='remove', job_id=stored_job_id)
```

The `cronjob` tool is enabled in the `enabled_toolsets` so the agent can
self-terminate. Adding a new cron job from a cron run is prohibited, but
removing yourself is fine.

### Alternative: Keep the job, just go silent

If you want the loop to remain for future regressions:
- Don't self-cancel
- Instead respond with `[SILENT]` when goal is met and no new work exists
- The job continues to check on cadence but stays quiet until the goal
  regresses

## Monitoring and Bail-Out

Goal loops can get stuck. Monitor the first 3-5 runs, then spot-check weekly.

### Bail-out signals (after which you should cancel the job)

- 3 consecutive ticks with no progress (STATE.md shows no changes)
- Acceptance rate drops below 30%
- The loop starts touching files it shouldn't (permission scope creep)
- Token cost per tick exceeds 3x your estimate
- The checker repeatedly passes but you find bugs manually (gate is rotten)

### How to bail out

```python
# Find the job
cronjob(action='list')

# Cancel it
cronjob(action='remove', job_id='THE_JOB_ID')
```

## Pitfalls

- **Checker and worker use the same model.** This is the #1 failure mode.
  The checker must be a different model or at minimum a different subagent
  with no access to the worker's reasoning.
- **Goal condition is too vague.** "Make it better" can never be objectively
  verified. Use a test, lint, build, or type check.
- **Worker produces no real output.** An "analysis" that changes nothing is
  the agent agreeing with itself. Verify the worker actually shipped a
  change.
- **Forgetting to update STATE.md.** Tomorrow's run restarts from zero,
  re-derives everything, burns tokens re-learning what yesterday already
  figured out.
- **No hard stop per tick.** Without one, a single tick can spiral and burn
  the entire day's token budget.
- **Using this for judgment-call work.** Architecture, auth, payments —
  keep /goal loops on machine-checkable changes only.
- **Not monitoring the first runs.** Goal loops that look correct but fail
  silently (Ralph Wiggum) are only caught by human observation.

## Quick Reference

```
                  ┌───────────────────────────┐
                  │  /goal loop decision      │
                  └───────────┬───────────────┘
                              │
                   ┌──────────▼──────────┐
                   │  pre-loop-checklist │
                   │  (4 conditions +    │
                   │   30-second test)   │
                   └──────┬───────┬──────┘
                          │       │
                        PASS     FAIL
                          │       │
                          │       └─────→ Don't build
                          │
                   ┌──────▼──────────────┐
                   │  Is goal objective  │
                   │  and machine-       │
                   │  checkable?         │
                   └──────┬───────┬──────┘
                          │       │
                         YES      NO
                          │       │
                          │       └─────→ Don't build
                          │
                          ▼
                   ┌──────────────┐
                   │  BUILD THE   │
                   │  GOAL LOOP   │
                   │              │
                   │  1. STATE.md │
                   │  2. Cron job │
                   │     (prompt  │
                   │     template)│
                   │  3. Monitor  │
                   │     first 3  │
                   │     runs     │
                   └──────────────┘
```
