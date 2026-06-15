---
name: pre-loop-checklist
description: "Gate before creating any cron job: run the 4-condition test + 30-second checklist to determine if loop engineering is worth the token cost. Source: 0xCodez loop engineering framework (June 2026), Anthropic engineering docs, Addy Osmani."
version: 1.0.0
author: Hermes Agent
license: Proprietary - All Rights Reserved
metadata:
  hermes:
    tags: [loop-engineering, cron, gates, automation, cost-control]
    source: "Adapted from Loop engineering: the 14-step roadmap from prompter to loop designer by 0xCodez (movez.substack.com)"
---

# Pre-Loop Checklist

Load this skill BEFORE creating any new cron job. It encodes the decision framework from
loop engineering: should this task be a loop, or should it stay as a manual prompt?

The honest answer: most developers don't need a loop yet. This checklist saves you from
building loops that cost more than they return.

## When to Use

- Before calling `cronjob(action='create', ...)`
- When a user says "schedule this" for a coding/automation task
- Before wrapping a manual task into an unattended loop

Skip this checklist for:
- Pure watchdog scripts (`no_agent=true`) — those don't use LLM tokens
- One-shot scheduled messages (e.g., "remind me at 9am") — no loop involved
- Non-coding cron jobs (weather reports, news briefs, daily summaries)

---

## Tier 1: The 4-Condition Test (Strategic)

Run this first. **Miss one condition and the loop costs more than it returns.**

### Condition 1: The task repeats at least weekly

"If the work does not recur weekly, you don't have a loop — you have a script you
ran once."

**Ask:** Will this task fire at least once per week?

- YES → continue to condition 2
- NO → keep it as a manual prompt or one-shot. A loop setup cost will never amortize.

### Condition 2: Verification is automated

"The loop needs something that can fail the work without you in the room."

**Ask:** Is there a test suite, type checker, linter, or build that can reject bad output?

- YES → continue to condition 3
- NO → STOP. A loop with no real check is the agent agreeing with itself on repeat.
  You're back in the chair reading every diff — the exact job the loop was
  supposed to remove.

### Condition 3: Your token budget can absorb the waste

"Loops re-read context, retry, explore. That burns tokens whether or not the run
ships anything."

**Ask:** If this loop burns 3-5x more tokens than a single manual run (retries,
re-reading context, exploration), will you still be happy?

- YES → continue to condition 4
- NO → STOP. The technique scales with budget. Solo builders on consumer plans
  get the token bill before the productivity gain.

### Condition 4: The agent has a reproduction environment

"The agent needs the ability to run the code it writes and see what breaks."

**Ask:** Can the agent actually run the code it changes? (test commands, build
toolchain, dev environment, logs)?

- YES → all 4 conditions met. Proceed to the 30-second checklist.
- NO → STOP. Without a reproduction environment, the loop iterates blind.

---

## Tier 2: The 30-Second Checklist (Tactical)

Only run this if all 4 strategic conditions passed. **Miss one box and keep it
as a manual prompt.**

- [1] **The task happens at least weekly.** Less than weekly → setup cost will
  never amortize.
- [2] **A test, type check, build, or linter can reject bad output.** No
  automated gate → the agent grades its own homework.
- [3] **The agent can run the code it changes.** No reproduction environment →
  iteration is blind.
- [4] **The loop has a hard stop.** Token budget, iteration count, or time limit.
  Without one, the loop runs until someone notices the bill.
- [5] **A human reviews before merge, deploy, or dependency changes.** Anything
  irreversible needs a human approval gate before action.

### Verdict

- All 5 boxes checked → **BUILD.** The task is right for loop engineering.
- 1-2 boxes unchecked → **FIX.** Address the gaps before building.
- 3+ boxes unchecked → **SKIP.** This task should stay as a manual prompt.

---

## Good First Loops vs. Bad First Loops

### Safe to loop (machine-checkable, bounded scope)

- **CI failure triage** — nightly, scan failures, classify causes, draft fix PRs
- **Dependency bump PRs** — weekly, scan for updates, test compatibility, open PRs
- **Lint-and-fix passes** — on every PR open event, apply style fixes
- **Flaky test reproduction** — loop until a theory survives the test
- **Issue-to-PR drafts** on code with strong test coverage

### Do NOT loop (judgment calls, irreversible, vague)

- Architecture rewrites
- Auth or payments code
- Production deploys
- Vague product work
- Anything where "done" is a judgment call

---

## After You Build: Track Cost Per Accepted Change

The metric that matters is **cost per accepted change**, not tokens spent or tasks
attempted. If your acceptance rate is below 50%, the loop is losing money.

Add to the cron job's state file (see cron-job-workflows skill for STATE.md template):

```
## Efficiency
- Runs this month: _
- Changes accepted: _
- Acceptance rate: _%
```

---

## Who Wins, Who Loses (Economics)

### Wins (build loops)

- Teams with repetitive, machine-checkable work and the budget to run it
- Codebases with strong existing test suites
- Async-first teams with multi-agent patterns already in use

### Loses (skip it today)

- **Solo builders on consumer plans** — token bill arrives before productivity
- **No automated verification** — loop with no real check is self-agreement
- **Review capacity is the bottleneck** — loop generates more code, makes queue longer

For one-off tasks, exploratory work, or anything where "done" is a judgment call,
**a single well-aimed prompt still wins.** Loop engineering is real, and most
developers don't need it yet.

---

## Common Failure Modes (Reference)

When reviewing existing cron jobs, check for these. See cron-job-workflows skill
for the Ralph Wiggum pattern and mitigation.

| Failure mode | Signal | Fix |
|---|---|---|
| No real verifier | Second agent asked to "review" with no test/lint/build | Add objective gate |
| Self-preferential bias | Maker grades own homework (same model writes and checks) | Separate verifier subagent, different model |
| Goal drift | Constraints disappear at turn 47 in long sessions | Re-read AGENTS.md or VISION.md each run |
| Agentic laziness | Loop declares "done enough" at partial completion | /goal with objective stop condition checked by fresh model |
| Ralph Wiggum | Loop exits on half-done job, no one notices | Hard gate (test/build/lint), not subjective review |
| Comprehension debt | Code ships faster than anyone reads diffs | Read diffs. Spot-check gates. Block architecture work. |

---

## Pitfalls

- **Skipping the 4-condition test.** Most developers fail at least one condition.
  Step 2 in the article exists for a reason.
- **One agent doing both writing and verifying.** Self-preferential bias. The maker
  grades its own homework and it's always "A+."
- **No state file.** Tomorrow's run restarts from zero instead of resuming.
- **Vague stop conditions.** "Done when it looks good" never holds. Use a test,
  a type pass, or a passing build.
- **No token budget cap.** Loops re-read context and retry. Without a cap,
  ambitious loops burn 5-10x the tokens you expected.
- **Running loops on a consumer plan with heavy verification.** Token bill or
  rate limit, one of them gets you.
- **Loops on judgment-call work.** Architecture, auth, payments, vague product
  decisions. Keep the loop on lint-and-fix, not strategy.
- **Not reading the diffs.** Comprehension debt at compound interest. The day you
  debug a system no one has read costs more than the tokens ever did.

---

## Quick Reference Card

```
                 ┌─────────────────────────┐
                 │   Should I loop this?   │
                 └───────────┬─────────────┘
                             │
                    ┌────────▼────────┐
                    │  4-condition    │
                    │  test passed?   │
                    └────┬───────┬────┘
                         │       │
                        YES      NO
                         │       │
                         │       └──────→ Keep as manual prompt
                         │
                ┌────────▼────────┐
                │  30-second      │
                │  checklist?     │
                └────┬───────┬────┘
                     │       │
                    ALL      NOT
                  BOXES     ALL
                     │       │
                     │       └──────→ Fix gaps or skip
                     │
                     ▼
                ┌─────────┐
                │  BUILD  │
                │  THE    │
                │  LOOP   │
                └─────────┘
```
