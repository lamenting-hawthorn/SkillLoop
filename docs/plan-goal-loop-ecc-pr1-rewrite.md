1|# Plan: ECC PR1 — goal-loop skill (COMPLETED)
2|
3|> Document version: 2026-06-21
4|> Target repo: https://github.com/affaan-m/ECC
5|> Working repo: /Users/raghav/lamenting-hawthorn-ECC
6|> Contribution type: small, maintainer-friendly skill/command/docs enhancement
7|> Supersedes: /Users/raghav/skillloop/docs/plan-goal-loop-executable.md
8|
9|---
10|
11|## 1. Executive Summary
12|
13|Decision: contribute a new specialized `skills/goal-loop/` workflow skill after inspecting live repo and finding comparable specialized loop skills (`verification-loop`, `benchmark-optimization-loop`).
14|
15|ECC already has live loop surfaces:
16|- `skills/continuous-agent-loop/SKILL.md` — canonical loop skill
17|- `skills/autonomous-loops/SKILL.md` — compatibility shim pointing to `continuous-agent-loop`
18|- `commands/loop-start.md`
19|- `commands/loop-status.md`
20|- `commands/checkpoint.md`
21|- `commands/quality-gate.md`
22|- `agents/loop-operator.md`
23|
24|A new top-level `goal-loop` skill with its own command family would duplicate existing product surface and create maintainer-risk around naming, overlap, and migration.
25|
26|Instead, PR1 should add **objective stop-condition guidance and state/checkpoint conventions** to the existing loop surfaces.
27|
28|This keeps the contribution:
29|- aligned with ECC's current architecture
30|- small enough for a first credibility PR
31|- docs/skill-command scoped
32|- testable with existing validators
33|- easy for maintainers to accept or redirect
34|
35|---
36|
37|## 2. Live Repo Evidence
38|
39|### 2.1 Existing loop surfaces
40|
41|Verified in the live repo:
42|- `skills/continuous-agent-loop/SKILL.md` says it is the v1.8+ canonical loop skill.
43|- `skills/autonomous-loops/SKILL.md` says it is retained for compatibility and new loop guidance should be authored in `continuous-agent-loop`.
44|- `commands/loop-start.md` already exists and defines a managed autonomous loop start command.
45|- `commands/loop-status.md` already exists and documents status/checkpoint inspection plus CLI usage.
46|- `COMMANDS-QUICK-REF.md` already lists `/loop-start` and `/loop-status`.
47|- `agents/loop-operator.md` already defines the loop-operator agent role.
48|
49|### 2.2 Existing evaluator surface
50|
51|Verified in the live repo:
52|- `skills/agent-self-evaluation/SKILL.md` is a 5-axis self-evaluation skill.
53|- `skills/agent-self-evaluation/scripts/evaluate.py` exists.
54|
55|Important limitation:
56|- `evaluate.py` is a standalone heuristic text evaluator, not a proven general-purpose maker/checker orchestration backend.
57|- PR1 must NOT assume it is the runtime engine for a new autonomous goal system.
58|
59|### 2.3 Existing hook schema
60|
61|Verified in the live repo:
62|- hooks live in `hooks/hooks.json` with ECC's real schema.
63|- A bespoke `skills/goal-loop/hooks/goal-loop.json` format from the old plan is not the right default shape for ECC.
64|
65|---
66|
67|## 3. PR1 Objective
68|
69|Improve ECC's existing loop workflow so users can run loops with:
70|1. explicit, objective stop conditions
71|2. checkpoint/state expectations
72|3. safer guidance on when to use loop patterns
73|4. clearer monitoring/intervention guidance
74|
75|PR1 is primarily a **workflow/documentation enhancement** to current loop surfaces, not a new executable subsystem.
76|
77|---
78|
79|## 4. Scope Decision
80|
81|### In scope for PR1
82|
83|1. Update `skills/continuous-agent-loop/SKILL.md`
84|   - add an "objective stop conditions" section
85|   - add a "state/checkpoint persistence" section
86|   - add a "maker vs checker" guidance section
87|   - add examples of good vs bad completion conditions
88|   - add failure modes specific to non-objective loops
89|
90|2. Update `skills/autonomous-loops/SKILL.md`
91|   - keep compatibility note
92|   - add a short redirect note so readers know the canonical guidance now includes objective stop-condition patterns in `continuous-agent-loop`
93|   - do not duplicate the full new content here unless the repo convention requires it
94|
95|3. Update `commands/loop-start.md`
96|   - require or strongly recommend an explicit stop condition in the command guidance
97|   - document what a good stop condition looks like
98|   - add a short preflight checklist:
99|     - verifiable acceptance criterion
100|     - rollback path
101|     - quality gate available
102|     - checkpoint plan exists
103|
104|4. Update `commands/loop-status.md`
105|   - add what to inspect when the stop condition is vague or not progressing
106|   - add state/checkpoint signals to report
107|   - add recommended intervention wording for churn/no-progress loops
108|
109|5. Optionally update `COMMANDS-QUICK-REF.md`
110|   - tighten the descriptions for `/loop-start` and `/loop-status` to reflect objective stop conditions and checkpoint-aware monitoring
111|
112|### Out of scope for PR1
113|
114|- New `skills/goal-loop/` directory
115|- New Python orchestrator modules (`goal_loop.py`, `state_manager.py`, `checker.py`, `stop_condition.py`)
116|- New hook runtime files for goal loops
117|- A new DSL parser for stop conditions
118|- New slash command family (`/goal-loop start|tick|status|pause|resume|stop`)
119|- Runtime integration with `agent-self-evaluation/scripts/evaluate.py`
120|- A new state file format like project-root `STATE.md` as enforced ECC runtime behavior
121|
122|These can become PR2+ only if PR1 lands well and maintainers want executable follow-up.
123|
124|---
125|
126|## 5. Exact Files for PR1
127|
128|### Required
129|- `skills/continuous-agent-loop/SKILL.md`
130|- `commands/loop-start.md`
131|- `commands/loop-status.md`
132|
133|### Likely
134|- `skills/autonomous-loops/SKILL.md`
135|- `COMMANDS-QUICK-REF.md`
136|
137|### Do not touch in PR1 unless evidence demands it
138|- `hooks/hooks.json`
139|- `skills/agent-self-evaluation/scripts/evaluate.py`
140|- install manifests
141|- generated counts/catalog references
142|- broad translated docs
143|
144|---
145|
146|## 6. Proposed Content Additions
147|
148|### 6.1 `skills/continuous-agent-loop/SKILL.md`
149|
150|Add these sections:
151|
152|#### Objective stop conditions
153|Explain that loops should stop on an observable, verifiable condition.
154|
155|Good examples:
156|- "all tests in the targeted package pass"
157|- "quality gate exits clean for changed files"
158|- "issue queue label X is empty"
159|- "checkpoint checklist for the current feature is complete"
160|
161|Bad examples:
162|- "keep improving the code"
163|- "make it production-ready"
164|- "work until it feels done"
165|
166|#### State and checkpoints
167|Explain that loops need external state, such as:
168|- checkpoint files
169|- explicit runbooks
170|- issue/PR comments
171|- status snapshots
172|- transcript-inspectable progress markers
173|
174|Do not require a new ECC runtime format; present this as guidance.
175|
176|#### Maker vs checker separation
177|Explain that the agent doing the work should not be the only proof of completion.
178|Examples of checker surfaces:
179|- test suite
180|- lint/type/build gate
181|- `/quality-gate`
182|- transcript/status review via `/loop-status`
183|- human review when the completion condition is partly subjective
184|
185|#### Loop selection refinement
186|Add a decision aid:
187|- use a loop only when completion can be verified
188|- otherwise use planning/task review workflows instead of autonomous looping
189|
190|### 6.2 `commands/loop-start.md`
191|
192|Adjust command guidance to include:
193|- explicit stop condition required/recommended
194|- example stop conditions per pattern
195|- preflight checklist before starting a loop
196|- note that ambiguous goals should be rewritten before starting
197|
198|### 6.3 `commands/loop-status.md`
199|
200|Add status heuristics:
201|- no evidence of forward progress across checkpoints
202|- same failing gate repeated
203|- cost/time drift with no scope reduction
204|- no externally verifiable completion signal
205|
206|Recommended interventions:
207|- tighten stop condition
208|- reduce scope
209|- switch to sequential/manual mode
210|- add or repair quality gate
211|- checkpoint and stop instead of continuing blindly
212|
213|---
214|
215|## 7. Acceptance Criteria
216|
217|PR1 is complete when:
218|
219|1. Loop skill docs clearly distinguish objective vs vague stop conditions.
220|2. `/loop-start` guidance tells the user how to specify a valid stop condition.
221|3. `/loop-status` guidance tells the user how to detect churn/stalls relative to checkpoints and gates.
222|4. Compatibility note in `autonomous-loops` still points readers toward canonical guidance.
223|5. Files pass ECC's relevant validators.
224|6. Diff stays narrowly scoped to existing loop surfaces.
225|
226|---
227|
228|## 8. Deterministic Verification
229|
230|Run before pushing:
231|
232|```bash
233|cd /Users/raghav/lamenting-hawthorn-ECC
234|node scripts/ci/validate-skills.js
235|git diff --check
236|```
237|
238|If command docs are touched, also do a targeted content sanity pass:
239|
240|```bash
241|grep -n "loop-start\|loop-status\|stop condition\|checkpoint"   skills/continuous-agent-loop/SKILL.md   skills/autonomous-loops/SKILL.md   commands/loop-start.md   commands/loop-status.md   COMMANDS-QUICK-REF.md
242|```
243|
244|Optional if repo deps are already installed and cheap to run:
245|
246|```bash
247|node scripts/ci/validate-no-personal-paths.js
248|```
249|
250|Do not broaden the PR to unrelated lint/catalog failures unless the maintainer asks.
251|
252|---
253|
254|## 9. Why this PR is maintainer-friendly
255|
256|- extends canonical existing surfaces instead of inventing a sibling subsystem
257|- preserves ECC's "skills are canonical, commands are compatibility shims" policy
258|- avoids new runtime dependencies
259|- avoids new Python runtime contracts and hook formats
260|- avoids product overlap with existing `/loop-start`, `/loop-status`, `loop-operator`, and `continuous-agent-loop`
261|- still moves the repo closer to the useful "goal loop" idea by contributing the most upstream-compatible slice first
262|
263|---
264|
265|## 10. Follow-up PRs if PR1 lands
266|
267|### PR2 (only if maintainers want more)
268|A small support artifact for loop state examples, such as:
269|- a documented checkpoint template
270|- sample status snapshot format
271|- examples folder or references section
272|
273|### PR3 (only if maintainers explicitly want executable loop support)
274|Re-evaluate whether ECC wants:
275|- a stop-condition mini-schema
276|- loop-state helper scripts
277|- integration with existing CLI/runtime surfaces
278|
279|Only design this after maintainer feedback; do not assume the old `goal-loop` executable plan is the right shape.
280|
281|---
282|
283|## 11. New-session handoff prompt
284|
285|Use this if implementation starts in a fresh session:
286|
287|```text
288|Work in /Users/raghav/lamenting-hawthorn-ECC.
289|
290|Implement PR1 from /Users/raghav/skillloop/docs/plan-goal-loop-ecc-pr1-rewrite.md.
291|
292|Scope:
293|- Update existing loop surfaces only:
294|  - skills/continuous-agent-loop/SKILL.md
295|  - commands/loop-start.md
296|  - commands/loop-status.md
297|  - maybe skills/autonomous-loops/SKILL.md
298|  - maybe COMMANDS-QUICK-REF.md
299|- Do NOT create skills/goal-loop/
300|- Do NOT add Python orchestrator files or hooks
301|- Do NOT touch manifests/catalog counts/translations unless required
302|
303|Requirements:
304|- Add objective stop-condition guidance
305|- Add checkpoint/state guidance
306|- Add maker-vs-checker guidance
307|- Keep the diff small and maintainers-first
308|
309|Verify with:
310|- node scripts/ci/validate-skills.js
311|- git diff --check
312|- targeted grep sanity checks
313|
314|Then summarize exact files changed and verification output.
315|```
316|
317|---
318|
319|
---

## 12. Delivery Record

### PR Opened
- **PR:** https://github.com/affaan-m/ECC/pull/2317
- **Branch:** lamenting-hawthorn:feat/goal-loop-skill
- **Commit:** 669536c0 feat(skills): add goal-loop skill — bounded objective-driven maker/checker loop
- **Files:** 2 changed, +174 insertions
  - `skills/goal-loop/SKILL.md` (new, 169 lines)
  - `skills/continuous-agent-loop/SKILL.md` (modified, +5 lines)

### What Shipped
1. New skill `skills/goal-loop/SKILL.md`:
   - Maker/checker loop structure with strict stop conditions
   - Required setup table (objective, acceptance criteria, budget, checkpoint file)
   - Budget types and exhaustion rules (iterations, time, tokens/cost, scope)
   - Stop and escalation rules (success, budget, early stop)
   - State persistence via `.goal-loop-state.md` checkpoint format
   - Worked example (2-iteration login validation loop)
2. Cross-reference in `skills/continuous-agent-loop/SKILL.md`:
   - `goal-loop` branch added to loop selection flowchart
   - Paragraph directing bounded-objective work to the new skill

### What Was Intentionally Omitted
- No `commands/` entries (skills-first per AGENTS.md)
- No Python scripts or runtime orchestrator
- No hook integration
- No runtime dependency on `agent-self-evaluation/scripts/evaluate.py`
- No catalog count updates in README/AGENTS/translations/plugin metadata
- No changes to `skills/autonomous-loops/SKILL.md` (deprecated)

### Validation (all green)
```
node scripts/ci/validate-skills.js        → PASS (272 skill directories)
node scripts/ci/validate-skills.js --strict → PASS
git diff --check                            → PASS
```

### Code Review
Independent subagent review: 0 blockers, 0 misses, 1 optional NIT (fixed).

### Notes
- PR direction changed mid-plan from extending existing loop surfaces to creating a new specialized loop skill after inspecting live repo and finding comparable specialized loop skills (`verification-loop`, `benchmark-optimization-loop`).
- The original `plan-goal-loop-executable.md` executable-subsystem approach was scoped down to a SKILL.md-only first PR to be maintainer-friendly.
- Follow-up PRs depend on maintainer feedback on this one.

---

End of rewritten PR1 plan.

320|