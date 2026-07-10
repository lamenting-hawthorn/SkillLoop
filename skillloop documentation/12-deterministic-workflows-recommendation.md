# Deterministic Workflows: Build or Not? — Executive Recommendation

**Date:** 2026-06-21
**Question:** Will a deterministic workflow layer increase SkillLoop's capability or bloat it?
**Answer:** Build it, but as a **modular, opt-in checkpoint/review system** — not as a universal governor.

---

## The Honest Verdict

**It will INCREASE capability if done minimally. It will DECREASE capability if done universally.**

The research is consistent across decades of software projects:

- **OpenAI** abandoned rigid deterministic dialogue constraints pre-ChatGPT because they fought the probabilistic substrate and imposed an "alignment tax" on flexibility.
- **AutoGPT** died in production because its rigid plan→execute→repeat loop became a token-burning, error-amplifying bottleneck with no safe stopping points.
- **IBM BPM / BEA AquaLogic** became massive shelfware because universal process governance stalled real work — teams routed around it with shadow IT.
- **LangGraph** succeeds in production precisely because teams use state machines **selectively** (for checkpointing, human-in-the-loop, retries) — not as a universal default.

**The pattern:** Governance layers improve systems when they are **localized, opt-in, and lightweight**. They kill systems when they are **universal, mandatory, and heavy**.

---

## What "Done Right" Looks Like for SkillLoop

### DO Build (Minimal, High-Value)

| Feature | Why | Effort |
|---------|-----|--------|
| **Checkpoint/replay for loop iterations** | If a 6-hour loop crashes at hour 5, resume from last checkpoint instead of restarting. This is pure capability gain. [Technical design →](13-checkpoint-replay-technical-design.md) | 2-3 days |
| **One interrupt gate before `apply`** | Pause before mutating code/memory. Surface diff + rationale. Wait for explicit approval. This is SkillLoop's core safety model made robust. | 3-4 days |
| **Deterministic evaluation as gate condition** | Use existing `eval/rubric.py` scores to auto-reject low-quality loop outputs before they reach review. No new architecture needed. | 1-2 days |

### DO NOT Build (Universal, Heavy)

| Feature | Why Not |
|---------|---------|
| **Universal state machine governing ALL agent actions** | Every tool call, every thought, every plan mutation would need a state transition. This is the bloat that killed AutoGPT and IBM BPM. |
| **YAML workflow DSL with 15 states** | If a user needs to write YAML to use SkillLoop, you've lost. SkillLoop should work out of the box, not require workflow engineering. |
| **Sub-workflows, parallel branches, time-based transitions** | These are Temporal/LangGraph features. SkillLoop is a learning governor, not a workflow orchestrator. |

---

## The Practical Difference

**Without the minimal layer:**
- A loop runs for 3 hours, crashes, loses all progress. User rage-quits.
- A bad skill gets applied to the codebase because the user batch-approved 20 proposals without reading them. Trust is broken.
- An enterprise customer asks "Can you guarantee the agent won't delete files without approval?" You say "Well, we have rubrics..." They say no.

**With the minimal layer:**
- Loop crashes? Resume from checkpoint. User says "oh, nice."
- Bad skill blocked by rubric gate before it ever reaches review queue. User trusts the system.
- Enterprise customer asks the same question. You say "Yes. The agent cannot mutate state without passing a deterministic evaluation and explicit human approval." They buy.

---

## The One-Sentence Recommendation

**Add checkpointing + one interrupt gate + rubric-based auto-reject. Do NOT add a universal state machine. This gives you 90% of the governance value with 10% of the architecture cost.**

---

## What to Skip Entirely

1. **Workflow engine with nodes/edges/transitions** — Use LangGraph or Temporal if you ever need this. SkillLoop should call them, not become them.
2. **YAML workflow definitions** — Configuration is complexity. Convention over configuration.
3. **Universal deterministic replay** — LLM outputs are stochastic. Replaying a loop will produce different results. Checkpoint the *state*, not the *outputs*.

---

## Suggested Implementation Order

1. **Week 1:** Add SQLite checkpointing to `loop.py` — save state before/after each iteration
2. **Week 1:** Add `resume` command to CLI — `skillloop resume --trace-id <id>`
3. **Week 2:** Wire `eval/rubric.py` score into controller — auto-reject if score < threshold before review
4. **Week 2:** Add one interrupt before `apply` — pause, show diff + rationale, require explicit approval
5. **Stop here.** Measure usage. If users ask for more workflow features, then consider LangGraph integration.

---

## Why This Is Not a Competitive Risk

LangGraph and Temporal already exist. If SkillLoop users need complex workflows, they should use LangGraph and plug SkillLoop in as the evaluation/review worker. SkillLoop's moat is **deterministic evaluation + dataset export + human review** — not workflow orchestration.

Trying to own the workflow layer means competing with LangChain and Temporal directly. That's a losing battle. Owning the **governance layer that sits inside any workflow** — that's the open niche.

---

**Bottom line:** Build the safety net, not the choreography. Your users want to know the agent won't hurt itself or their codebase. They don't want to write YAML to define how it thinks.
