# Deep Dive: Top 5 Actions for SkillLoop

**Date:** 2026-06-18  
**Based on:** Analysis of 10 articles + SkillLoop codebase (`rubric.py`, `skills.py`, `controller.py`, `loop.py`, `review/queue.py`, `schema.py`)  

---

## Action 1: Ship Retrieval-Quality Evaluators

### Current State
SkillLoop's `eval/rubric.py` scores traces on:
- Tool call success/failure
- User correction keywords ("wrong", "incorrect", "don't")
- Learning signal keywords ("remember", "i prefer")
- Error/success language in assistant text
- Presence of final answer

What it does NOT evaluate:
- Whether the agent retrieved the right context before answering
- Whether semantic search buried the correct answer
- Whether the user had to manually specify files because `@Codebase` failed
- Whether retrieved chunks contained secrets or generated artifacts

### The Problem
Across all 10 articles analyzed, **retrieval failure is the #1 hidden cause of poor agent performance.** Cursor's `@Codebase` is praised for speed but not accuracy. Noisy's Obsidian system has no retrieval quality gates. Mem0 retrieves but does not score. When an agent gives a wrong answer because it retrieved the wrong context, current evaluators blame the model or the tool — not the retrieval layer.

This means SkillLoop currently misses the highest-leverage learning signal: **the gap between what the agent knew and what it needed to know.**

### Concrete Implementation

#### 1A. New `eval/retrieval.py` module

Create `skillloop/eval/retrieval.py` with the following evaluator:

```python
EVALUATOR_NAME = "retrieval_quality"
EVALUATOR_VERSION = "1.0"

# Scoring dimensions (0-100 each, weighted average)
DIMENSIONS = {
    "coverage": 0.30,        # Did retrieval include the file/section that contains the answer?
    "ranking": 0.25,         # Was the correct chunk in the top-3 retrieved?
    "precision": 0.20,       # Were retrieved chunks free of secrets/generated noise?
    "recency": 0.15,         # Was the retrieved content from the latest version?
    "relevance": 0.10,       # Did the retrieved content actually help answer the user query?
}
```

**Evidence collection logic:**

1. **Coverage:** Compare the files the agent read (via tool calls) against the files a human would have read to answer the same query. Use git history, file names in the query, and `@Files` overrides as ground truth.
   - If the user manually specified `@Files`, mark coverage as failed (the agent should have found them).
   - If the agent read files not mentioned in the query or answer, mark as over-retrieval.

2. **Ranking:** If the trace contains a retrieval tool call with multiple results, check whether the result the agent actually used was in the top-ranked positions.
   - Requires: retrieval tool calls to include ranked results in `result` or `artifact_refs`.

3. **Precision:** Scan retrieved content for:
   - Secrets (reuse `sanitize.redact_secrets` patterns)
   - Generated artifacts (`.gitignore` patterns, build outputs)
   - Binary files
   - If any found, score = 0 for this dimension.

4. **Recency:** Check `mtime` or git commit date of retrieved files vs. query timestamp. If retrieved file is >30 days old and a newer version exists, penalize.

5. **Relevance:** Use a lightweight heuristic: did the assistant's final answer cite or reference the retrieved files? If the agent retrieved 5 files but the answer references none, relevance is low.

#### 1B. Integration into `controller.py`

In `controller_tick()`, after the evaluation loop, add:

```python
# Retrieval-quality evaluation (optional, adapter-dependent)
if policy.evaluation.retrieval_evaluator and policy.ingestion.adapter in {"hermes-db", "cursor"}:
    from skillloop.eval.retrieval import evaluate_retrieval
    for trace in store.list_traces():
        retrieval_eval = evaluate_retrieval(trace, project_root=store.root)
        store.save_evaluation(retrieval_eval)
```

#### 1C. Schema extension

Add to `Evaluation`:
```python
retrieval_score: int | None = None  # 0-100
retrieval_dimensions: dict[str, int] | None = None  # per-dimension breakdown
```

#### 1D. CLI output

`skillloop status` should show:
```
Retrieval quality (last 7 days):
  coverage:    72%  (12 traces had missing context)
  ranking:     81%  (3 traces had correct answer buried)
  precision:   95%  (1 trace retrieved a .env file)
  recency:     68%  (8 traces used stale files)
```

### Acceptance Criteria
- [ ] `eval/retrieval.py` exists and has unit tests (`test_eval_retrieval.py`)
- [ ] Evaluator scores 0-100 with per-dimension breakdown
- [ ] If user manually specified files (`@Files`), coverage dimension = 0
- [ ] If retrieved content contains secrets, precision dimension = 0
- [ ] `skillloop status` displays retrieval quality metrics
- [ ] Does not require LLM calls (fully deterministic)

### Estimated Effort
**2–3 weeks** (1 engineer). Most complexity is in ground-truth inference (what files *should* have been retrieved). This requires adapter-specific logic for Hermes (tool call patterns) and Cursor (file read patterns).

### Dependencies
- Adapter-specific retrieval tool call parsing (Hermes uses `web_search`, `read_file`, `browser_snapshot`; Cursor uses `@Codebase`, `@Files`)
- Project root access for `.gitignore` and git history

---

## Action 2: Make Review UX Sub-10-Seconds

### Current State
`review/queue.py` has three functions:
- `list_pending(store)` — returns raw `Proposal` objects
- `approve_proposal(store, proposal_id)` — sets status to "approved"
- `reject_proposal(store, proposal_id)` — sets status to "rejected"

Proposals are written as markdown files to `.skillloop/approved/`. The user reviews them by:
1. Running `skillloop review list` (CLI table)
2. Reading raw markdown files
3. Running `skillloop review approve <id>` or `reject`

There is no diff view, no side-by-side comparison with the current skill/memory, no plain-English rationale, and no batch operations.

### The Problem
From the Codex-maxxing analysis: "The side panel for shared artifact review is genuinely delightful." From the Opik analysis: "Side-by-side diff replay is best-in-class." From the Factory 2.0 analysis: "Approval gates are human-in-the-loop decisions written to state."

SkillLoop's review UX is the **highest-friction part of the pipeline.** If approving a proposal takes 30 seconds of reading raw markdown, users will batch-approve or skip review entirely. This defeats the core safety model.

### Concrete Implementation

#### 2A. Diff generation for skill proposals

In `review/diff.py`:

```python
def generate_skill_diff(proposal: Proposal, current_skills_dir: Path) -> str:
    """Generate a unified diff between the proposed skill and the current skill with the same name."""
    # Parse proposal.content for the `name:` frontmatter field
    proposed_name = parse_frontmatter_name(proposal.content)
    current_path = current_skills_dir / f"{proposed_name}.md"
    
    if not current_path.exists():
        return f"# New skill: {proposed_name}\n\n{proposal.content}"
    
    current_content = current_path.read_text()
    return unified_diff(current_content, proposal.content, fromfile=current_path.name, tofile=f"{proposed_name}.proposed.md")
```

#### 2B. Plain-English rationale extraction

In `review/rationale.py`:

```python
def extract_rationale(proposal: Proposal, evaluation: Evaluation) -> str:
    """Generate a one-paragraph plain-English summary of why this proposal exists."""
    parts = []
    parts.append(f"This proposal was generated from trace {proposal.trace_id[:8]} (score: {evaluation.score}/100).")
    
    if "user_correction" in evaluation.tags:
        parts.append("The user corrected the agent during this trace, suggesting a durable improvement.")
    if "tool_failure" in evaluation.tags:
        parts.append("The trace contained failed tool calls; the proposal may add error-handling guidance.")
    if "learning_signal" in evaluation.tags:
        parts.append("The user expressed a preference that could be codified as a principle.")
    
    parts.append(f"Source: {proposal.reason}")
    return " ".join(parts)
```

#### 2C. Enhanced `skillloop review` CLI

New subcommands:

```bash
# Interactive review with diff + rationale
skillloop review interactive
# Shows:
#   [1/5] Proposal: proposed-workflow-abc123
#   Rationale: This proposal was generated from trace abc123 (score: 85/100). 
#              The user corrected the agent during this trace...
#   Diff:
#   @@ -5,3 +5,4 @@
#    - Do not save credentials
#   + - Always verify the file exists before reading
#   
#   Approve? [y/n/s(skip)/q(quit)]

# Batch approve low-risk proposals (score > 90, no user_correction, no tool_failure)
skillloop review batch-approve --min-score 90 --exclude-tags user_correction,tool_failure --dry-run

# Side-by-side view for memory proposals
skillloop review show <id> --side-by-side
```

#### 2D. Web-based review UI (optional, P1)

A minimal local HTTP server (`skillloop review serve`) that renders:
- Proposal cards with score badges
- Syntax-highlighted diffs
- One-click approve/reject buttons
- Filter by kind (skill/memory), score range, tags

### Acceptance Criteria
- [ ] `skillloop review interactive` walks through pending proposals with diff + rationale
- [ ] `skillloop review batch-approve` supports `--min-score`, `--exclude-tags`, `--dry-run`
- [ ] Review time per proposal < 10 seconds for simple changes
- [ ] Diff view shows exactly what changed vs. current skill/memory
- [ ] Rationale is auto-generated from evaluation evidence (no LLM required)

### Estimated Effort
**2–3 weeks** (1 engineer) for CLI enhancements. **+4–6 weeks** for web UI.

### Dependencies
- None. All data is in `SkillLoopStore`.

---

## Action 3: Build the iii Worker Adapter

### Current State
SkillLoop has two adapters:
- `generic_jsonl` — reads JSONL files
- `hermes` — reads Hermes state DB

There is no adapter for Mike Piccolo's `iii` engine (formerly Motia), which is gaining traction as a language-agnostic orchestration engine for agent harnesses.

### The Problem
From the Piccolo analysis: "Most teams do not build an agentic backend — they adopt a monolithic framework and later suffer." iii solves this by decomposing the harness into replaceable workers connected by `iii.trigger()`.

If SkillLoop is not available as an iii worker, teams using iii will build their own learning layer (or skip governance entirely). If SkillLoop IS available as a worker, it becomes infrastructure — not a competing platform.

### Concrete Implementation

#### 3A. New `adapters/iii.py` module

```python
"""iii (Motia) worker adapter for SkillLoop.

Registers as an iii worker with:
- skillloop::ingest — triggered after each turn by the observability worker
- skillloop::evaluate — triggered on schedule or after N traces
- skillloop::proposals — returns pending proposals for review
- skillloop::apply — triggered after human approval
"""

import json
from pathlib import Path
from typing import Any

from skillloop.controller import controller_tick
from skillloop.policy import SkillLoopPolicy
from skillloop.review.queue import approve_proposal, list_pending, write_approved_files
from skillloop.schema import AgentTrace
from skillloop.store import SkillLoopStore

WORKER_NAME = "skillloop"
WORKER_VERSION = "1.0"


def register_worker(iii_registry: Any, project_root: Path, policy_path: Path) -> None:
    """Register SkillLoop as an iii worker."""
    store = SkillLoopStore(project_root)
    policy = SkillLoopPolicy.from_file(policy_path)
    
    @iii_registry.worker("skillloop::ingest")
    def ingest_handler(payload: dict[str, Any]) -> dict[str, Any]:
        """Ingest a trace from the observability worker."""
        trace = AgentTrace.from_dict(payload["trace"])
        trace_id = store.save_trace(trace)
        return {"trace_id": trace_id, "status": "ingested"}
    
    @iii_registry.worker("skillloop::evaluate")
    def evaluate_handler(payload: dict[str, Any]) -> dict[str, Any]:
        """Run evaluation and distillation."""
        report = controller_tick(store, policy)
        return {
            "run_id": report.id,
            "traces_evaluated": report.summary.get("traces_evaluated", 0),
            "proposals_created": report.summary.get("proposals_created", 0),
            "requires_review": report.summary.get("requires_review", 0),
        }
    
    @iii_registry.worker("skillloop::proposals")
    def proposals_handler(payload: dict[str, Any]) -> dict[str, Any]:
        """Return pending proposals for review."""
        pending = list_pending(store)
        return {
            "count": len(pending),
            "proposals": [p.to_dict() for p in pending],
        }
    
    @iii_registry.worker("skillloop::apply")
    def apply_handler(payload: dict[str, Any]) -> dict[str, Any]:
        """Apply approved proposals (called after human approval)."""
        approved = write_approved_files(store)
        return {"applied": [str(p) for p in approved]}
```

#### 3B. iii trigger integration

Document how to wire SkillLoop into a iii harness:

```typescript
// In the iii harness worker
import { trigger } from 'iii';

async function afterTurn(turnResult) {
  // 1. Send trace to SkillLoop
  await trigger('skillloop::ingest', { trace: turnResult.toTrace() });
  
  // 2. Check if proposals are pending
  const proposals = await trigger('skillloop::proposals', {});
  if (proposals.count > 0) {
    // 3. Route to approval-gate worker
    await trigger('approval-gate', { 
      proposals: proposals.proposals,
      approveCallback: 'skillloop::apply',
    });
  }
}
```

#### 3C. Configuration

Add to `SkillLoopPolicy`:

```yaml
adapters:
  iii:
    enabled: true
    worker_name: "skillloop"
    trigger_prefix: "skillloop::"
    auto_evaluate_after_n_traces: 10
    auto_evaluate_after_minutes: 60
```

### Acceptance Criteria
- [ ] `adapters/iii.py` exists with `register_worker()`
- [ ] Four iii handlers: ingest, evaluate, proposals, apply
- [ ] Documentation: `docs/iii-integration.md` with wiring examples
- [ ] Example iii project in `examples/iii-harness/`
- [ ] Unit tests for each handler

### Estimated Effort
**3–4 weeks** (1 engineer). Requires understanding iii's worker registration API, which is still evolving.

### Dependencies
- iii engine installed locally for testing
- `SkillLoopPolicy` schema extension for adapter config

---

## Action 4: Add Steering-Signal Detection

### Current State
`eval/rubric.py` detects user corrections via keyword matching:

```python
CORRECTION_WORDS = ("wrong", "incorrect", "no,", "actually", "don't", "do not")
LEARNING_WORDS = ("remember", "i prefer", "always", "never")
```

When detected:
- Score -= 15
- Tag = "user_correction"
- Note = "User correction detected; candidate for learning, but quality is lower."

What it does NOT do:
- Fast-track the trace to distillation
- Capture the specific correction as a structured learning signal
- Distinguish between "steering" (mid-flight direction) and "correction" (post-hoc complaint)
- Trigger immediate memory proposal generation without waiting for the evaluation loop

### The Problem
From the Codex-maxxing analysis: "Steering corrections should bypass the score threshold and go straight to proposal generation." Jason Liu treats steering as the highest-value learning signal because it is:
- **Specific** ("make this smaller" is actionable)
- **Timely** (captured during the task, not after)
- **Context-rich** (the agent knows what it was doing when corrected)

Current SkillLoop treats steering the same as any other user correction — it penalizes the score and moves on. This wastes the richest learning signal in the entire trace.

### Concrete Implementation

#### 4A. Distinguish steering from correction

In `eval/rubric.py`, split the detection:

```python
STEERING_WORDS = ("make this", "change this to", "use", "switch to", "try", "instead")
CORRECTION_WORDS = ("wrong", "incorrect", "no,", "actually", "don't", "do not")
LEARNING_WORDS = ("remember", "i prefer", "always", "never")

def classify_user_signal(message: str) -> str:
    lowered = message.lower()
    if any(word in lowered for word in STEERING_WORDS):
        return "steering"
    if any(word in lowered for word in CORRECTION_WORDS):
        return "correction"
    if any(word in lowered for word in LEARNING_WORDS):
        return "preference"
    return "none"
```

#### 4B. Steering-signal evidence type

Add to `evidence.py`:

```python
def steering_evidence(messages: list[Message]) -> list[dict]:
    """Extract steering signals with context."""
    evidence = []
    for i, message in enumerate(messages):
        if message.role != "user":
            continue
        signal_type = classify_user_signal(message.content)
        if signal_type == "steering":
            # Capture context: what was the assistant doing before this?
            prior_assistant = None
            for j in range(i - 1, -1, -1):
                if messages[j].role == "assistant":
                    prior_assistant = messages[j].content[:200]
                    break
            evidence.append({
                "kind": "steering_signal",
                "message_index": i,
                "instruction": message.content,
                "prior_assistant_summary": prior_assistant,
                "priority": "high",
            })
    return evidence
```

#### 4C. Fast-track distillation for steering signals

In `loop.py`, modify `run_outer_loop()`:

```python
# After evaluation, check for steering signals
for evaluation in evaluations:
    if any(e["kind"] == "steering_signal" for e in evaluation.evidence):
        # Bypass score threshold for steering traces
        trace = store.get_trace(evaluation.trace_id)
        steering_proposals = propose_steering_memory(trace, evaluation)
        for proposal in steering_proposals:
            store.save_proposal(proposal)
        summary.proposals_created += len(steering_proposals)
```

New `distill/steering.py`:

```python
def propose_steering_memory(trace: AgentTrace, evaluation: Evaluation) -> list[Proposal]:
    """Generate memory proposals from steering signals.
    
    Unlike generic memory distillation, steering proposals are:
    - Specific to the task context
    - High priority (user explicitly directed the agent)
    - Actionable (contain the exact instruction)
    """
    proposals = []
    for evidence_item in evaluation.evidence:
        if evidence_item["kind"] != "steering_signal":
            continue
        
        instruction = evidence_item["instruction"]
        prior = evidence_item.get("prior_assistant_summary", "")
        
        content = f"""---
name: steering-{trace.id[:8]}
description: User steering signal captured during task execution.
priority: high
context: "{prior}"
---

# Steering Memory

## Trigger
When the agent is in a similar context to: "{prior}"

## Direction
{instruction}

## Rationale
This instruction was given mid-flight by the user and represents a durable preference.
"""
        proposals.append(Proposal(
            trace_id=trace.id,
            kind="memory",
            title=f"Steering: {instruction[:60]}",
            content=content,
            reason=f"User steering signal: {instruction}",
            source_trace_schema_version=trace.schema_version,
        ))
    return proposals
```

#### 4D. CLI integration

```bash
# Show steering signals from recent traces
skillloop steering list --since 24h

# Output:
# Trace abc123 (score: 45 → override to 80 for distillation)
#   Steering: "make this smaller" at turn 3
#   Prior context: "Building a Docker image..."
#   Proposal: steering-abc123 (pending review)

# Approve all steering proposals
skillloop steering approve-all --dry-run
```

### Acceptance Criteria
- [ ] Steering signals detected separately from corrections and preferences
- [ ] Steering traces bypass `min_score` threshold for distillation
- [ ] `distill/steering.py` generates structured memory proposals with context
- [ ] `skillloop steering list` shows steering signals with prior context
- [ ] Unit tests for steering detection, evidence extraction, and proposal generation

### Estimated Effort
**1.5–2 weeks** (1 engineer). Mostly additive; no breaking changes to existing pipeline.

### Dependencies
- None.

---

## Action 5: Publish the "Governance Gap" Narrative

### Current State
SkillLoop has:
- A `README.md` with architecture and CLI docs
- A `docs/` folder with `architecture.md`, `safety.md`, `trace-schema.md`
- No public content strategy
- No comparison content vs. other systems
- No named concept for the problem SkillLoop solves

### The Problem
The market does not know it needs governance. Every article we analyzed treats auto-mutation as the default and review gates as optional. If SkillLoop only speaks to users who already want governance, it will never reach the 99% of teams who do not yet know they need it.

The 10 articles prove that **the governance gap is real, urgent, and unaddressed.** We need to name it, document it, and own the conversation.

### Concrete Implementation

#### 5A. Define the "Governance Gap" framework

Create `docs/governance-gap.md`:

```markdown
# The Governance Gap

## Definition
The Governance Gap is the space between what an agent loop *does* and what its operators *know about what it did*.

## Symptoms
1. **Auto-mutation without review** — The agent writes memory, deploys code, or updates skills without human approval.
2. **Evaluation without ground truth** — Quality is measured by user reactions (thumbs up/down) or implicit signals (did the user ask again?), not by deterministic criteria.
3. **Training without provenance** — Models are fine-tuned on data whose origin, quality, and context are unknown.
4. **Scale without safety** — More agents, more loops, more automation — but no increase in oversight.

## The Four Layers of Governance
1. **Observability** — Can you see what happened? (tracing, logging)
2. **Evaluation** — Can you score what happened against criteria? (rubric-based, deterministic)
3. **Review** — Can a human approve or reject before state changes? (diffs, rationale, batch ops)
4. **Export** — Can you turn governed traces into training data? (SFT/DPO with manifests)

Most systems solve Layer 1. SkillLoop solves Layers 1–4.
```

#### 5B. Publish article series

**Article 1: "The Governance Gap in Agent Engineering"**
- Target: Hacker News, X, Lobste.rs
- Hook: "Every agent framework ships with auto-mutation. None ship with review gates."
- Content: Define the gap, name the symptoms, show examples from Cursor/Factory/Mem0/Opik
- CTA: "SkillLoop is the first learning governor built for review-before-apply."

**Article 2: "Why Auto-Write Memory is Technical Debt"**
- Target: ML engineers, agent builders
- Hook: "Your agent just learned something. Do you know what? Do you agree?"
- Content: Compare Mem0's auto-write vs. SkillLoop's proposal queue. Show a real example where auto-write corrupted a skill.

**Article 3: "Deterministic Evaluation is the Only Evaluation"**
- Target: MLOps, eval engineers
- Hook: "LLM-as-a-judge is not evaluation. It is a second opinion."
- Content: Explain why rubric-based, evidence-backed scoring is necessary for training data. Show how SkillLoop's evaluators work.

**Article 4: "Your Agent Loop is a Data Pipeline"**
- Target: Data engineers, fine-tuning teams
- Hook: "If you are not exporting training data from your agent loops, you are burning money."
- Content: Show how SkillLoop turns traces into SFT/DPO datasets with manifests. Compare to systems that have no export pipeline.

#### 5C. Create comparison matrix

Add to README or a dedicated `docs/comparison.md`:

| Dimension | SkillLoop | Mem0 | Cursor | Factory 2.0 | Opik | Codex |
|-----------|-----------|------|--------|-------------|------|-------|
| Auto-write memory | ❌ Review first | ✅ Auto | N/A | ✅ Auto | N/A | ✅ Auto |
| Deterministic eval | ✅ Rubric | ❌ None | ❌ None | ❌ None | ❌ Traces only | ❌ Tests only |
| Dataset export | ✅ SFT/DPO | ❌ None | ❌ None | ❌ None | ❌ None | ❌ None |
| Training configs | ✅ TRL/Unsloth/Axolotl | ❌ None | ❌ None | ❌ None | ❌ None | ❌ None |
| Secret redaction | ✅ At ingestion | ❌ None | ❌ None | ❌ None | ❌ None | ❌ None |
| Local-first | ✅ SQLite | ❌ Cloud | ❌ Cloud | ❌ Cloud | ❌ Cloud | ❌ Cloud |
| Vendor-neutral | ✅ Adapters | ❌ Mem0 only | ❌ Cursor only | ❌ Factory only | ❌ Comet only | ❌ OpenAI only |

#### 5D. Talks and community

- Submit to **AI Engineer Summit**, **NeurIPS workshops**, **ICML MLOps track**
- Host a **"Governance Gap" meetup** (virtual or at major conferences)
- Create a **Discord/Slack community** for agent governance discussions
- Publish a **monthly "State of Agent Governance"** newsletter

### Acceptance Criteria
- [ ] `docs/governance-gap.md` defines the framework and four layers
- [ ] Article 1 published and promoted on HN/X
- [ ] Comparison matrix live in README or docs
- [ ] At least one talk submission to a major conference
- [ ] Newsletter or community channel launched

### Estimated Effort
**2–3 weeks** (0.5 engineer for writing + 0.5 engineer for community). Mostly writing and promotion, not code.

### Dependencies
- None. Can start immediately.

---

## Summary: Priority and Timeline

| Action | Effort | Impact | Risk if Delayed | Priority |
|--------|--------|--------|-----------------|----------|
| 1. Retrieval-quality evaluators | 2–3 weeks | High | Miss the #1 user pain point | P0 |
| 2. Review UX sub-10-seconds | 2–3 weeks | High | Users skip review, safety model collapses | P0 |
| 3. iii worker adapter | 3–4 weeks | Medium-High | Competitors own the integration point | P1 |
| 4. Steering-signal detection | 1.5–2 weeks | High | Waste the richest learning signal | P0 |
| 5. Governance gap narrative | 2–3 weeks | Medium | Market never learns it needs governance | P1 |

**Recommended sprint plan:**
- **Sprint 1 (weeks 1–2):** Actions 4 (steering) + 2 (review UX MVP: diff + rationale)
- **Sprint 2 (weeks 3–4):** Action 1 (retrieval eval) + review UX polish (batch-approve)
- **Sprint 3 (weeks 5–6):** Action 3 (iii adapter) + Action 5 (article 1 + comparison matrix)
- **Sprint 4 (weeks 7–8):** Action 5 (articles 2–4 + talks) + iii adapter testing

Total: **8 weeks to close the competitive gaps** identified across all 10 articles.
