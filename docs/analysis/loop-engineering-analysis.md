# Deep Analysis: Addy Osmani's Loop Engineering vs SkillLoop/Hermes

**Source:** Addy Osmani (@addyosmani) on X, June 8, 2026. 836K views, 11.5K bookmarks, 4.8K likes.
**Core quote:** "Loop engineering is replacing yourself as the person who prompts the agent. You design the system that does it instead."

---

## 1. What's genuinely good about this post/idea?

**The paradigm shift is real and important.**

Addy correctly identifies that the leverage point has moved from "writing better prompts" to "designing the system that generates prompts." This is a genuine phase change in how agentic work gets done — not hype.

**The outer loop framing is precise.** He distinguishes the inner agentic loop (perceive→reason→act→observe on each turn) from the outer loop (scheduled automation that runs the harness on a timer, spawns helpers, feeds itself). This mental model is actually useful and matches how production agent systems fail.

**The 5 building blocks + memory are concrete and actionable:**
1. Automations (scheduled triggers)
2. Worktrees (parallel isolation)
3. Skills (project knowledge persistence)
4. Plugins/connectors (tool integration)
5. Sub-agents (maker/verifier split)
6. Memory (durable state outside context window)

This is a real architecture, not hand-waving.

**The risks section is honest.** He explicitly calls out that verification is still on you, comprehension debt grows faster, and cognitive surrender is the "comfortable failure." Most AI thought leaders don't caveat their frameworks this directly.

---

## 2. What's well done — what makes it work?

**It names a real pattern that was already happening.** People were doing loop engineering before Addy named it (Steinberger, Cherny, the HumanLayer folks). Naming it gives practitioners a shared vocabulary and accelerates adoption of the pattern.

**It positions loop engineering as the third layer in a stack:**
- Prompt engineering → single turn
- Context engineering → conditions around one answer
- Loop engineering → autonomous system across many turns

This layering makes it clear that loop engineering doesn't replace the previous layers — it wraps them.

**It's tool-agnostic by design.** Addy explicitly points out the shape is identical across Claude Code and OpenAI Codex. This is a valuable insight: the loop design matters more than which agent tool you use.

**The maker/verifier sub-agent split is the most important architectural insight.** One agent drafts, a separate agent reviews. This is essentially what SkillLoop's eval→distill→review→apply pipeline does, but at the agent orchestration level rather than the trace learning level.

---

## 3. What can be taken directly into SkillLoop/Hermes?

**The 6-component taxonomy maps almost 1:1 onto SkillLoop's architecture:**

| Loop Engineering | SkillLoop/Hermes |
|-----------------|------------------|
| Automation | Hermes cron/scheduler triggers |
| Worktrees | Hermes subagent isolation |
| Skills | Hermes skills (existing) |
| Connectors/MCP | Hermes MCP integrations |
| Sub-agents (maker/verifier) | SkillLoop eval→distill→review pipeline |
| Memory | Hermes memories (existing) |

**Directly adoptable patterns:**

1. **Scheduled eval triggers.** Addy mentions "an automation runs every weekday morning on the repo." SkillLoop could add a cron-style eval that runs on a schedule and auto-files issues for traces that drop below quality thresholds.

2. **The maker/verifier split as a first-class concept.** SkillLoop's eval→distill pipeline is essentially this: one agent (eval) scores, another (distill) proposes, a human reviews. This matches exactly.

3. **Worktree-style parallel subagent isolation.** Hermes subagents already do this to some degree, but the worktree pattern (isolated git branches per subagent) could make subagent runs safer.

4. **Memory as a first-class component.** The insight that "the model forgets everything between runs, so the state has to live on disk" is the core insight behind Hermes memories. It's good validation that this is the right architectural choice.

---

## 4. What can be improved by taking inspiration from it?

**Hermes's outer loop is implicit.** There's no explicit construct for "run this harness on a schedule." The cron integration exists but isn't framed as the primary loop driver. Addy's framing would make this more intentional.

**SkillLoop's "apply" is manual and local.** Addy describes a loop where connectors auto-update tickets, open PRs, etc. SkillLoop v1 explicitly doesn't write outside `.skillloop/approved/`. This is the right conservative choice for v1, but the architecture should anticipate automated application of approved changes.

**No explicit "done" condition / eval gate.** Addy mentions /goal in Claude Code ("run until a verifiable condition holds") — SkillLoop could add a declarative "stop condition" to the eval schema: a boolean signal that means "this trace is good enough, stop iterating."

**The eval→distill coupling is too loose.** In Addy's model, verification happens continuously (the loop checks each result). In SkillLoop, eval and distill are separate commands. The loop concept would tighten this into a continuous pipeline.

---

## 5. If you fully adopt this, what will go WRONG?

**If SkillLoop/Hermes tried to implement full loop engineering today:**

**Cost explosion.** Addy explicitly flags "token economics can swing wildly." A naive implementation of "run the eval loop continuously" could burn through context windows and API calls. SkillLoop is designed for offline, local-first evaluation — a full loop would need cost controls that don't exist yet.

**Premature automation of apply.** Addy describes connectors that "open the PR and update the ticket" — but SkillLoop's conservative boundary (approved artifacts only, no direct Hermes writes) exists for good reason. Full adoption would need security hardening (permissions, audit logging) that the MVP doesn't have.

**Comprehension debt at the skill level.** Addy: "the faster the loop ships code you didn't write, the bigger the gap." SkillLoop creates skills from traces — if those skills encode patterns the engineer doesn't understand, you get skill-level comprehension debt on top of trace-level debt.

**Cognitive surrender becomes the default.** If the loop runs and produces artifacts, there's pressure to just accept them. The review step exists in SkillLoop precisely to prevent this — but if reviews become rubber stamps, the whole system degrades.

**The orchestrator becomes a single point of failure.** If the outer loop has a bug, it runs the wrong thing at scale, faster. With a manual prompting workflow, mistakes are bounded by human speed.

---

## 6. If you adopt it, what will go RIGHT?

**If SkillLoop/Hermes selectively adopts loop engineering principles:**

**The eval gate becomes the loop condition.** Instead of "run eval once on demand," you get "run eval continuously and auto-fail traces below threshold." This is exactly what Addy means by "the loop decides whether the result is acceptable."

**Skills compound correctly.** Addy's insight is that skills should contain "exit criteria" — not vague instructions, but concrete checklists. SkillLoop's distillation could be enhanced to output skill files with explicit exit criteria rather than just general guidance.

**The memory layer gets validated by production use.** Hermes memories exist as a concept, and loop engineering proves they're load-bearing for long-running agentic systems. SkillLoop's trace→memory pipeline would benefit from explicit "what did the loop learn this week" summaries.

**Subagent coordination becomes explicit.** The maker/verifier split is Addy's most concrete architectural contribution. SkillLoop already does this internally (eval vs distill), but Hermes could expose this as a first-class pattern for multi-subagent workflows.

**Evaluation becomes the primary signal.** Addy says "the loop's 'it's done' means something" only if you have a verifier. SkillLoop's deterministic eval rubric is the right foundation for this — it's just not yet wired as a loop condition.

---

## 7. How does this compare to what SkillLoop/Hermes already does better?

**SkillLoop is already doing the inner loop right.** The eval→distill→review→apply→export pipeline is essentially Addy's maker/verifier pattern applied to trace learning, not code output. SkillLoop just does it at the data layer instead of the agent layer.

**Hermes already has the memory layer.** Addy calls memory "the trick every long-running agent depends on." Hermes already has memories. This is validation, not a new idea.

**SkillLoop's conservative boundary is a feature, not a gap.** Addy: "build the loop like someone who intends to stay the engineer." SkillLoop's explicit choice not to auto-apply to Hermes, not to touch existing architecture, not to run fine-tuning automatically — this is exactly the "stay the engineer" posture.

**Where Hermes/SkillLoop needs work vs. Addy's vision:**

| Gap | Addy's vision | Current Hermes/SkillLoop |
|-----|--------------|-------------------------|
| Outer loop scheduling | Explicit cron/automation triggers | Implicit (via cron, but not framed as loop) |
| Done conditions | Verifiable stop criteria | Basic score, not declarative conditions |
| Connector layer | MCP-based tool integration | MCP exists, but not loop-aware |
| Apply automation | Auto-PR/ticket updates | Manual approve→apply only |
| Cost awareness | Instrumented token usage | Not in MVP |

---

## Verdict

Addy Osmani's Loop Engineering is a high-quality, well-named articulation of a real pattern that production agent practitioners have been converging on. It's not revolutionary — it's the right name for work that was already happening (Steinberger, Cherny, HumanLayer, Anthropic's harness design docs).

**For SkillLoop/Hermes specifically:** The overlap is significant. The 5 building blocks + memory map cleanly onto existing Hermes concepts. The maker/verifier split is already implemented in SkillLoop's pipeline. The main gap is explicit outer-loop scheduling and done conditions — these would tighten the eval gate from "on-demand check" to "continuous condition."

**The right move:** Don't adopt loop engineering wholesale. Take the taxonomy (it validates what you already built), the done-condition pattern (add this to the eval schema), and the maker/verifier framing (explicitly name this in the architecture docs). Keep the conservative apply boundary. Add cost awareness before adding unattended automation.

The post's greatest value for SkillLoop is as architecture validation: what you're building is the right thing, and now it has a name that the industry understands.

---

## 8. Implemented Hermes Skills (June 10, 2026)

Based on this analysis, three operational Hermes skills were built to bridge the
loop engineering concepts into the Hermes runtime. These live in
`~/.hermes/skills/system/` and load into Hermes sessions — they are NOT part of
SkillLoop (architecture rule #1: never rebuild Hermes subsystems).

### pre-loop-checklist

`~/.hermes/skills/system/pre-loop-checklist/SKILL.md`

Gate to load before any `cronjob(action='create')`. Encodes the 4-condition test
(repeats weekly? automated verification? token budget? reproduction environment?)
plus a 30-second tactical checklist, good/bad first loop examples, and a failure
mode reference card. Verdict: most developers don't need a loop yet.

### cron-job-workflows (patched)

`~/.hermes/skills/system/cron-job-workflows/SKILL.md`

Existing skill, patched with three loop-engineering additions:
- **STATE.md template** — the persistent file outside the conversation that holds
  progress, lessons learned, and efficiency tracking (cost per accepted change)
- **Ralph Wiggum loop detection** — how to detect loops that fail quietly
- **Red Flags — Never Do These** — 10 concrete prohibitions (soft stop
  conditions, self-grading, judgment-call work, etc.)

### goal-loop

`~/.hermes/skills/system/goal-loop/SKILL.md`

Full implementation of the `/goal` primitive as a Hermes cron pattern. Four-part
architecture: cron tick → read STATE.md → checker subagent (different model) →
goal met? report + self-cancel : worker subagent → update STATE.md → loop again.
Includes prompt template, self-cancellation logic, and bail-out signals.

### Future: SkillLoop loop-engineering evaluator (P1/P2)

A SkillLoop evaluator that scores traces on loop engineering hygiene — gated on
cost tracking being added first. Would check:
- Was pre-loop-checklist loaded before cron job creation?
- Does the loop use maker/checker split with different models?
- Is STATE.md being maintained?
- Is acceptance rate above 50%?
- Any Ralph Wiggum signals (soft completion, self-grading)?
