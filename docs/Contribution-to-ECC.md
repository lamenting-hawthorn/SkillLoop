# Contribution Opportunities to ECC

> Document version: 2025-06-20
> Based on SkillLoop re-review (new features: dataset readiness, fs-safety boundaries, secret redaction, launchd service runner, policy-driven controller, controller audit reports)
> Our existing merged PRs: #2220 (agent-self-evaluation skill + agent-evaluator persona), #2235 (tdd-workflow security hardening)

---

## Summary

After re-reviewing SkillLoop's latest capabilities (post-MVP additions including filesystem safety, secret redaction, dataset readiness gating, launchd service integration, and the policy-driven autonomous controller), the following 8 contribution opportunities to ECC remain valid and have been enriched. Two new opportunities emerged from the latest SkillLoop features.

---

## 1. goal-loop Skill — Maker-Checker with Externalized State

**Impact: HIGH | Feasibility: MEDIUM | Est: 2-3 days**

**Why ECC needs it:**
ECC has `autonomous-loops` (sequential pipelines, PR loops, DAGs) and `continuous-agent-loop`, but nothing with the **maker-checker split** + **STATE.md persistence** pattern. This is a proven SkillLoop primitive for tasks that need an independent verifier before the next execution step.

**What to build:**
A `goal-loop` skill that implements:
- Cron-fired or manually triggered loop: read `STATE.md` → checker model evaluates stop condition → worker executes one step → update `STATE.md`
- Checker is read-only, independent model; worker mutates state
- Stop condition DSL: `score_gte`, `required_tags`, `forbidden_tags`, `max_iterations`
- Resume-not-restart: `STATE.md` survives session restarts and can be committed to git
- Integration with `agent-self-evaluation` (our PR #2220) to trigger `/harness-audit` on stall

**Files to create:**
- `skills/goal-loop/SKILL.md`
- `skills/goal-loop/templates/STATE.md`

**SkillLoop origin:** `goal-loop/SKILL.md` reference skill (cites 0xCodez loop engineering framework + Anthropic evaluator-optimizer pattern)

---

## 2. session-evaluator Skill — Backward-Looking Session Scoring

**Impact: HIGH | Feasibility: MEDIUM | Est: 2-3 days**

**Why ECC needs it:**
ECC's `eval-harness` is forward-looking (define evals before coding). This is backward-looking: "score the session that just happened." It complements `/verify` (which checks code state) by evaluating the *agent's process* (did it verify? did it redact secrets? did it run tests? did it stay within scope?).

**What to build:**
A `session-evaluator` skill that:
- Scores completed sessions on 5 dimensions: `correctness`, `completeness`, `verification`, `security_hygiene`, `efficiency`
- Uses observable signals only — command execution, test execution, file artifacts, user corrections — no LLM guesswork
- Emits JSON output with `score`, `tags[]`, `evidence[]`, `provenance`
- Integrates with existing `agent-self-evaluation` skill and `agent-evaluator` persona (our PR #2220)
- Can be invoked after `/sessions` or at session end

**Files to create:**
- `skills/session-evaluator/SKILL.md`

**SkillLoop origin:** `skillloop/eval/rubric.py`, `eval/registry.py`, `eval/evidence.py`

---

## 3. context-governor Skill — Token-Aware Compaction

**Impact: HIGH | Feasibility: MEDIUM | Est: 2-3 days**

**Why ECC needs it:**
ECC issue #2155 is open and asks for `/compact` triggered by token % rather than just tool-call count. `context-budget` only *reports* overhead; `ecc-context-monitor` only *warns*. No skill actively compresses or deduplicates context during long sessions. Context management is the #1 production harness engineering problem across the ecosystem.

**What to build:**
A `context-governor` skill that:
- Monitors context window fill via pre/post-tool-use hooks
- Triggers strategic compaction at configurable thresholds (50%, 70%, 85%)
- Applies compression strategies: rule deduplication, CLAUDE.md slimming, MCP tool subsetting, sliding-window session summary
- Integrates with `continuous-learning-v2` to promote compressed insights to instincts instead of raw logs
- Offers `/context-governor` command with `--auto` and `--dry-run` modes

**Files to create:**
- `skills/context-governor/SKILL.md`
- Optional hook integration in `hooks/hooks.json`

**SkillLoop origin:** Hermes gateway event hooks + SkillLoop's understanding of trace/session boundaries

---

## 4. distill-review Skill — Human-in-the-Loop for Learning Artifacts

**Impact: MEDIUM-HIGH | Feasibility: MEDIUM | Est: 2-3 days**

**Why ECC needs it:**
ECC's `continuous-learning-v2` auto-extracts instincts via hooks with **no review gate**. Low-quality extractions can pollute agent memory. This skill adds a deliberate `pending → approved → exported` workflow, keeping the agent's memory clean.

**What to build:**
A `distill-review` skill that:
- Defines distillation triggers: user corrections, workflow descriptions ("when X then Y"), repeated patterns
- Formats proposals with `kind` (memory/skill), `title`, `content`, `reason`, `provenance`
- Provides review commands: list pending, approve/reject by ID prefix
- Deduplicates by content hash (don't propose same thing twice)
- Exports approved artifacts to project-local `.ecc/approved/`, **never** directly into `~/.claude/skills`
- Includes provenance metadata on every artifact: source trace, evaluator score, distiller version
- Adds filesystem safety: validates export paths stay within project root (inspired by SkillLoop `fs_safety.py`)

**Files to create:**
- `skills/distill-review/SKILL.md`

**SkillLoop origin:** `skillloop/distill/memory.py`, `review/queue.py`, `apply/filesystem.py`, `fs_safety.py`

---

## 5. fs-safety-guardrails Skill — Filesystem Boundary Enforcement

**Impact: HIGH | Feasibility: MEDIUM | Est: 2-3 days**
**NEW — emerged from SkillLoop re-review**

**Why ECC needs it:**
ECC has `security-review` and `supply-chain-incident-response`, but no skill that actively prevents path traversal, symlink escape, or unsafe file operations *during* agent sessions. With 261+ community skills and agent-generated file operations, a boundary-enforcement skill fills a critical gap.

**What to build:**
A `fs-safety-guardrails` skill that:
- Validates all file write/delete paths stay within the project root (path traversal prevention)
- Detects symlink escapes before following them
- Rejects absolute paths to sensitive directories (`~/.ssh/`, `~/.aws/`, `~/.config/`, `/secrets/`, `/credentials/`)
- Integrates with `pre:write` and `pre:delete` hook events
- Provides a `/fs-safety check [path]` command for manual validation
- Emits warnings with clear rationale when a path is rejected

**Files to create:**
- `skills/fs-safety-guardrails/SKILL.md`
- Optional: `hooks/fs-safety-guardrails.json` for automatic enforcement

**SkillLoop origin:** `skillloop/fs_safety.py` — `resolve_under_root()`, `ensure_not_symlink_escape()`, `safe_path_segment()`

---

## 6. session-sanitizer Hook/Skill — Automatic Secret Redaction

**Impact: HIGH | Feasibility: LOW-MEDIUM | Est: 1-2 days**
**NEW — emerged from SkillLoop re-review**

**Why ECC needs it:**
Agent sessions frequently handle API keys, tokens, and credentials. ECC has no systematic secret redaction in session transcripts, memory exports, or shared artifacts. This is a lightweight, high-value safety addition.

**What to build:**
A `session-sanitizer` skill/hook that:
- Scans session transcripts, memory exports, and shared artifacts for common secret patterns
- Redacts: `sk-...` keys, Bearer tokens, `api_key`/`token`/`secret`/`password` assignments
- Redacts absolute artifact references to sensitive paths (`~/.ssh/`, `~/.aws/`, etc.)
- Operates as a `Stop` phase hook: sanitizes before the session writes to `~/.claude/` or exports
- Provides `/session-sanitizer audit` to check current session for unredacted secrets
- Preserves data shape: redaction is in-place replacement, not deletion

**Files to create:**
- `skills/session-sanitizer/SKILL.md`
- `hooks/session-sanitizer.json` (Stop-phase hook)

**SkillLoop origin:** `skillloop/sanitize.py` — `redact_secrets()`, `redact_artifact_ref()`, `redact_data()`

---

## 7. data-readiness Skill — Dataset Validation Before Export

**Impact: MEDIUM-HIGH | Feasibility: MEDIUM | Est: 2 days**
**NEW — emerged from SkillLoop re-review**

**Why ECC needs it:**
ECC's `continuous-learning-v2` and `eval-harness` produce data, but there's no skill that validates whether a dataset is actually ready for training, sharing, or further processing. This prevents garbage-in-garbage-out in downstream workflows.

**What to build:**
A `data-readiness` skill that:
- Defines a `DatasetReadinessPolicy` with configurable checks: min records, min tokens, non-empty splits, metadata completeness, hash integrity
- Validates `*.jsonl` datasets against the policy
- Checks for absolute artifact references in metadata (privacy leak detection)
- Emits a `DatasetReadinessReport` with `ready` boolean, per-check pass/fail, warnings, and stats
- Integrates with `session-sanitizer` to catch unredacted secrets before dataset export
- Provides `/data-readiness check [path]` and `/data-readiness policy` commands

**Files to create:**
- `skills/data-readiness/SKILL.md`

**SkillLoop origin:** `skillloop/dataset_readiness.py` — `DatasetReadinessPolicy`, `DatasetReadinessReport`, `assess_dataset_readiness()`

---

## 8. controller-audit Skill — Durable Run Reports for Autonomous Loops

**Impact: MEDIUM-HIGH | Feasibility: MEDIUM | Est: 2-3 days**

**Why ECC needs it:**
ECC's `continuous-agent-loop` and `autonomous-loops` describe HOW to build loops, but provide no structured way to audit what happened during each loop iteration. When an autonomous agent runs overnight and produces unexpected results, there's no durable report to inspect.

**What to build:**
A `controller-audit` skill that:
- Defines a `ControllerRunReport` schema: `id`, `started_at`, `finished_at`, `policy`, `actions`, `errors`, `summary`
- Records each autonomous tick: ingestion count, evaluation results, dataset export status, proposal counts
- Stores reports in project-local `.ecc/audit/` (not global state)
- Provides `/controller-audit list`, `/controller-audit show [id]`, `/controller-audit latest` commands
- Integrates with `goal-loop` to append audit IDs to `STATE.md`
- Includes failure-path logging: if a tick errors, the report still captures what succeeded and what failed

**Files to create:**
- `skills/controller-audit/SKILL.md`
- `skills/controller-audit/templates/CONTROLLER_RUN_REPORT.md`

**SkillLoop origin:** `skillloop/controller.py` — `ControllerRunReport`, `controller_tick()`, `save_controller_report()`

---

## Quick Wins (same day / next day)

These are smaller fixes to existing ECC issues that don't require new skills but leverage our expertise:

| Issue | Fix | Est | Why it fits |
|-------|-----|-----|-------------|
| #2276 | `cost-report` skill reads wrong path/schema | ~2h | Our eval/verification experience |
| #2278 | `observe.sh` regex catastrophic backtracking (100% CPU hang) | ~2h | Our security-hardening work on PR #2235 |
| #2103 | "Before You Build" skill proposal | ~1 day | Content skill, unclaimed, easy merge |
| #2155 | Trigger `/compact` on token % not just tool-call count | ~1 day | Our context-management expertise |

---

## Recommended Execution Order

### Phase 1: Foundation (novel primitives)
1. **`goal-loop`** — Most novel contribution. No existing ECC skill covers maker-checker + STATE.md persistence. Fits ECC v2.0's state-store architecture.
2. **`session-evaluator`** — Completes the evaluation story started with PR #2220. PR #2220 = self-evaluation *during* tasks; this = structured scoring *after* sessions.

### Phase 2: Safety (high leverage, low risk)
3. **`session-sanitizer`** — Lightweight hook. High safety value. Builds on our PR #2235 security work.
4. **`fs-safety-guardrails`** — Boundary enforcement. Critical for 261+ community skills and agent-generated file operations.

### Phase 3: Governance (data quality + audit)
5. **`distill-review`** — Human-in-the-loop for learning artifacts. Prevents memory pollution.
6. **`data-readiness`** — Dataset validation gate. Prevents garbage-in-garbage-out.
7. **`controller-audit`** — Durable run reports for autonomous loops. Essential for debugging overnight runs.

### Phase 4: Infrastructure
8. **`context-governor`** — Token-aware compaction. Closes issue #2155 with a full skill rather than a minimal hook patch.

---

## Cross-Reference: SkillLoop Feature → ECC Contribution

| SkillLoop Feature | ECC Contribution | File in SkillLoop |
|---|---|---|
| `goal-loop` reference skill | `skills/goal-loop/` | `~/.hermes/skills/goal-loop/SKILL.md` |
| Eval rubric + evidence | `skills/session-evaluator/` | `skillloop/eval/rubric.py`, `eval/evidence.py` |
| Controller + policy | `skills/controller-audit/` | `skillloop/controller.py`, `policy.py` |
| Dataset readiness | `skills/data-readiness/` | `skillloop/dataset_readiness.py` |
| Filesystem safety | `skills/fs-safety-guardrails/` | `skillloop/fs_safety.py` |
| Secret redaction | `skills/session-sanitizer/` | `skillloop/sanitize.py` |
| Review queue | `skills/distill-review/` | `skillloop/review/queue.py` |
| Launchd service runner | N/A (platform-specific, not ECC-native) | `skillloop/service.py` |

---

## What NOT to Contribute

These SkillLoop features do not map well to ECC's markdown/JSON-only contribution model:

- **Launchd service runner** — Platform-specific Python runtime. ECC is markdown + JSON.
- **Training config generation** — Requires Python/TRL/Unsloth/Axolotl runtime. Out of scope for ECC.
- **Direct Hermes state.db ingestion** — Requires SQLite read access. ECC skills are self-contained markdown.
- **Fine-tuning dataset export (SFT/DPO)** — Requires structured data pipeline. ECC's scope is agent harness optimization, not ML training infrastructure.

---

## Notes

- All skill proposals follow ECC's existing SKILL.md template with YAML frontmatter.
- All hooks follow the `hooks/hooks.json` PreToolUse/PostToolUse/SessionStart/Stop matcher pattern.
- All contributions use ECC-native tools (Read, Grep, Glob, Bash) and avoid external dependencies.
- Verification before pushing: run `npm run lint`, `node scripts/ci/validate-skills.js`, and scoped Unicode safety scan on touched files.
