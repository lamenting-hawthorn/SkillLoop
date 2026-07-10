# Analysis: Self-Improving Agent Skills (Zach Lloyd / Warp) vs. SkillLoop

> **Source:** [Self-Improving Agent Skills: How to Build Feedback Loops That Compound Team Judgement](https://mer.vin/2026/06/self-improving-agent-skills-how-to-build-feedback-loops-that-compound-team-judgement)  
> **Author:** Mervin Praison, summarising Warp CEO Zach Lloyd's approach (June 2026)  
> **SkillLoop context:** Local-first learning governor for AI agent runtimes (Hermes sidecar). Ingests traces, evaluates them deterministically, distills memory/skill proposals, requires human review before apply, and exports SFT/DPO datasets. Does NOT auto-apply, auto-train, or mutate global agent state. Key modules: adapters, eval, distill, review, apply, export, controller, policy, loop, conditions.

---

## 1. Article Summary

Zach Lloyd's thesis is that agent skills should self-improve through **feedback loops**, not one-shot prompt tuning. The core loop is:

1. Agent runs from a version-controlled `SKILL.md` file (Markdown + YAML frontmatter).
2. Agent produces output + recommendation (e.g., a draft social reply).
3. Team reacts in Slack (emoji) or GitHub (comments).
4. A **daily learning agent** collects that feedback.
5. It extracts **principles** (not brittle rules) from the feedback.
6. It opens a **PR** updating the skill file.
7. A human reviews and merges; the loop restarts.

The article introduces Warp's internal agent **Buzz**, which monitors thousands of social mentions per month, triages them, drafts replies, and posts suggestions to Slack—while humans retain the final send action. The entire implementation is "zero lines of application code — skills only," orchestrated via Warp's **Oz** platform (cron, webhooks, API triggers).

Key architectural ideas:
- **Principles beat rules:** Principles transfer to unseen cases; rules overfit and crack on edge cases.
- **Two-floor skill design:** Floor 1 is the *work skill* (how to do the job); Floor 2 is the *learning skill* (how to generalise feedback into principle updates).
- **Seven-step learning procedure:** Identify → Ask why → Zoom out → Check existing principles → Write a principle → Place it correctly → Edit and commit.
- **Never auto-merge:** All durable skill changes go through PR review.

---

## 2. The Good

### 2.1 Principles Over Rules
The article makes a strong case for principles ("be helpful, not defensive") versus rule checklists ("if bug mention → say X"). Warp reports shrinking their skill file to ~1/5th the size while improving quality. This aligns well with SkillLoop's `distill` module, which is designed to abstract patterns from traces rather than hard-coding exceptions.

### 2.2 Human-in-the-Loop by Default
The insistence on **PR review for all skill changes** is excellent. "Never auto-merge skill changes" is a design rule that directly matches SkillLoop's `review` and `apply` modules, where human approval is a hard gate before any skill or memory mutation.

### 2.3 Version-Controlled Skills as Source of Truth
Treating `SKILL.md` files like code—with history, diff review, and rollback—is a mature operational pattern. SkillLoop similarly treats skills as artifacts that should be auditable and version-controlled, even though SkillLoop itself is a sidecar governor rather than a VCS.

### 2.4 Zero-Friction Feedback Channels
Embedding feedback where the team already works (Slack emoji, GitHub review threads) dramatically increases participation rates. This is a UX insight that SkillLoop's `adapters` module can learn from: the closer the feedback signal is to the user's existing workflow, the richer the training data.

### 2.5 Meta-Skill (Learning Skill) Concept
The "Floor 2 — learning skill" is a genuinely powerful abstraction. It separates *how to do the task* from *how to learn from feedback*, preventing the agent from turning every correction into a brittle exception. SkillLoop's `distill` module performs a similar function, but the article's explicit "learning skill" file is an elegant pattern that could inform SkillLoop's policy layer.

### 2.6 Scheduled, Not Real-Time, Learning
The daily batching of feedback into a single learning pass is pragmatic. It avoids noisy, reactive updates and gives the agent enough signal to detect patterns. SkillLoop's `loop` and `conditions` modules can adopt this cadence-based triggering rather than event-driven auto-learning.

---

## 3. The Bad

### 3.1 Tight Coupling to Warp's Proprietary Stack (Oz)
The implementation is essentially a vendor showcase for Warp Oz. The commands (`oz agent run-cloud`, `oz schedule create`) and the `.agents/skills/` convention are platform-specific. SkillLoop, by contrast, is runtime-agnostic and designed to work with any agent framework (Hermes, etc.) via its adapter layer.

### 3.2 No Deterministic Evaluation
The article describes extracting principles from feedback, but it does not describe **how to verify that a principle actually improves performance**. There is no eval harness, no regression testing, no A/B comparison of skill versions. SkillLoop's `eval` module is explicitly designed to close this gap by running deterministic checks on traces before and after a proposed change.

### 3.3 No Mention of Dataset Export or Model Training
The loop stops at updating a skill file. There is no path from "principles in Markdown" to **SFT/DPO datasets** or fine-tuned models. SkillLoop's `export` module is built for exactly this: converting approved skill/memory updates into structured training data for downstream model improvement.

### 3.4 Brittle Feedback Signal
Slack emoji and thread notes are lightweight, but they are also ambiguous. A 👍 could mean "good output" or "I agree with the triage decision" or "I sent the reply." The article does not discuss normalising or structuring this feedback. SkillLoop's `adapters` and `eval` modules are designed to ingest structured traces with explicit outcome labels, reducing ambiguity.

### 3.5 Single-Tenant, Single-Team Assumption
The Buzz example assumes one team, one Slack channel, one set of taste. There is no discussion of multi-team skill inheritance, skill merging, or handling conflicting feedback. SkillLoop's `policy` and `controller` modules are designed to handle governance across multiple users or teams.

### 3.6 No Rollback or Safety Mechanism Beyond Git
While Git provides history, the article does not discuss automated rollback if a merged skill change degrades performance. SkillLoop's `conditions` module can gate application on eval scores, and the `controller` can trigger rollbacks if regressions are detected post-merge.

---

## 4. What's Missing

| Missing Element | Why It Matters | SkillLoop's Equivalent |
|-----------------|----------------|------------------------|
| **Deterministic evaluation harness** | Without eval, you cannot distinguish a good principle update from a bad one. | `eval` module |
| **Structured trace ingestion** | Emoji reactions are too noisy to be a reliable training signal. | `adapters` module |
| **Dataset export for fine-tuning** | Skill files alone do not improve the underlying model weights. | `export` module (SFT/DPO) |
| **Multi-team governance** | Enterprises need skills that inherit, override, and merge across teams. | `policy` + `controller` |
| **Regression testing across skill versions** | A new principle might help case A but hurt case B. | `eval` + `conditions` |
| **Safety limits / budget guards** | No mention of rate-limiting learning passes or cost controls. | `controller` + `policy` |
| **Feedback provenance / attribution** | Who gave the feedback? When? Under what context? | Trace metadata in `adapters` |
| **Auto-rollback on degradation** | If a merged PR hurts performance, the system should self-correct. | `conditions` + `apply` reverse |

---

## 5. What SkillLoop Can Implement

### 5.1 Adopt the "Learning Skill" Pattern
SkillLoop's `distill` module can be augmented with an explicit **meta-prompt** (a "learning skill") that teaches the distillation agent how to generalise feedback into principle updates. This would live in the `policy` layer and would be user-customisable per skill.

### 5.2 Principle-Oriented Distillation
Update the `distill` module to prefer **principles** over **rules** when generating skill proposals. For example, instead of emitting "never mention pricing in the first sentence," it should emit "if someone is venting, lead with empathy, not a pitch." This can be enforced via the meta-prompt and validated in `eval`.

### 5.3 Batch/Cadence-Based Learning Trigger
SkillLoop's `loop` module currently supports event-driven and scheduled triggers. The article reinforces that **daily batching** is the right default for judgement work. SkillLoop should make `cron`-based learning the recommended pattern for social/support skills, with `conditions` to skip empty batches.

### 5.4 Slack/GitHub Adapter Enhancements
The `adapters` module should support lightweight feedback ingestion from Slack (emoji reactions, thread replies) and GitHub (review comments, PR reactions). The adapter should normalise these into structured trace annotations (e.g., `outcome: approved`, `outcome: rejected`, `note: "too salesy"`) before passing to `eval` and `distill`.

### 5.5 PR-Style Review UI for Skill Proposals
SkillLoop's `review` module should present proposed skill changes as a **diff** (like a PR), showing: which feedback was reviewed, which principle changed, and the exact diff to the skill file. This mirrors the article's "~60-second review" experience and makes human approval low-friction.

### 5.6 Skill File Format Compatibility
Support the Warp-style `SKILL.md` format (Markdown + YAML frontmatter) as a first-class skill artifact in SkillLoop. This lowers migration friction for teams already using Oz and makes SkillLoop a viable governance sidecar even for non-Hermes runtimes.

### 5.7 Export Principles to SFT/DPO Datasets
When a principle is approved and merged, SkillLoop's `export` module should generate training pairs:
- **SFT:** (context + old skill) → (context + new skill)
- **DPO:** (chosen: new behaviour, rejected: old behaviour)

This closes the loop from "skill file update" to "model weight improvement," which the article entirely omits.

---

## Conclusion

Zach Lloyd's feedback-loop architecture is conceptually sound and operationally proven at Warp. Its emphasis on **principles over rules**, **human-gated PR review**, and **meta-skills for learning** are directly compatible with SkillLoop's design philosophy. Where it falls short is in **evaluation rigor**, **structured trace ingestion**, and **downstream model training**—gaps that SkillLoop's modular pipeline (`adapters` → `eval` → `distill` → `review` → `apply` → `export`) is explicitly designed to fill.

SkillLoop should treat this article as **validation of the problem space** and **inspiration for UX patterns** (Slack feedback, diff-based review, learning skills), while continuing to differentiate on **deterministic safety**, **multi-team governance**, and **dataset export for model fine-tuning**.
