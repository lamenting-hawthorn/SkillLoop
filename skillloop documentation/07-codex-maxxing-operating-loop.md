# Analysis: Codex-maxxing vs. SkillLoop

> **Article:** [Codex-maxxing: treating Codex like an operating loop](https://jxnl.co/writing/2026/05/10/codex-maxxing)  
> **Author:** Jason Liu  
> **Date:** May 10, 2026  
> **Analyzed for:** SkillLoop documentation

---

## 1. Article Summary

Jason Liu describes a shift in how he uses OpenAI Codex: from a chat-based coding assistant to a **continuous operating loop** for knowledge work. The core insight is that agent usefulness stops being about "one prompt, one answer" and starts being about giving work a durable place to live, evolve, and keep moving after the human steps away.

Key concepts from the article:

| Concept | Description |
|---------|-------------|
| **Durable Threads** | Long-running, compacted "megathreads" pinned per workstream (Chief of Staff, Agents SDK, etc.) that accumulate history and preferences over months. |
| **Voice Input** | Feeding unedited, messy thinking into the agent rather than polished text. |
| **Steering** | Injecting new direction *while* the agent is already working, without waiting for each step to finish. |
| **Memory (Disk-Backed)** | An Obsidian vault (`TODO.md`, `people/`, `projects/`, `notes/`) kept as a GitHub repo so the agent writes durable memory as files, and humans review changes via diffs. |
| **Computer / Browser Use** | Three tiers: `$browser` (local web surfaces), `@chrome` (signed-in sessions), `@computer` (GUI automation). Plus Appshots for lightweight screenshot context. |
| **Remote Control** | Checking in from mobile to steer or approve long-running tasks. |
| **Heartbeats** | Recurring, thread-local automation: check Slack every 30 min, monitor PRs for feedback, wait on customer support queues, etc. |
| **Goals** | Long-running tasks with a *real finish line* and an oracle (e.g., "migrate Rich to Rust and pass all original unit tests"). |
| **Side Panel** | A shared surface where humans and agents inspect, annotate, and operate the same artifact (HTML, Storybook, Slidev, PDFs, spreadsheets) without breaking the loop. |

The overarching thesis: **The more Codex gets places to remember, revisit, inspect, and act, the less work dies between prompts.**

---

## 2. The Good (What Jason Gets Right)

### 2.1 The Operating Loop Mental Model
Liu nails the paradigm shift. Agents are not search engines or chatbots; they are **workers that need persistent context, steering, and review surfaces**. This aligns directly with SkillLoop's design as a sidecar governor for agent runtimes.

### 2.2 Memory as Files + Diffs
Saving memory to disk (Obsidian vault → GitHub repo) is a powerful pattern. Files force the agent to compress experience into a durable, inspectable form. Diffs become a review surface. This mirrors SkillLoop's `review/` and `apply/` modules, but Liu's implementation is manual and ad-hoc.

### 2.3 Verification-First Goals
The emphasis on **ambition with verification** is critical. A goal without an oracle is "just a wish." The Rich→Rust example (pass all original tests) is exactly the kind of observable evidence SkillLoop's `eval/` module should reward.

### 2.4 Steering as a UX Primitive
Steering (injecting intent mid-flight) is described as what makes voice useful. It turns a linear chat into a **queue-shaped conversation**. This is a strong human-in-the-loop pattern that SkillLoop can model explicitly: mid-flight corrections are high-signal learning events.

### 2.5 Heartbeats as Lightweight Recurrence
Heartbeats are a pragmatic take on automation: not cron jobs, but *thread-local* recurring checks that can adjust cadence, cross tool boundaries, and stop when conditions are met. The animation feedback loop (Slack → Remotion → `@computer` upload) is a compelling example of cross-tool orchestration.

### 2.6 Side Panel as Shared Context
The side panel is where Codex "stops being only a chat app and starts becoming the place the work happens." Shared artifact surfaces (HTML, Storybook, Slidev) let humans annotate what the agent sees. This is a strong argument for SkillLoop to support artifact rendering in its review workflow.

---

## 3. The Bad (Where Codex-maxxing Falls Short)

### 3.1 Vendor Lock-In and Opacity
The entire architecture is tightly coupled to OpenAI Codex: first-party memory, Skills system, Heartbeats, Goals, and Connectors. There is no portability. If the API changes, pricing shifts, or a better model appears, the accumulated "operating loop" context is trapped.

### 3.2 No Deterministic Evaluation
Liu reviews memory diffs manually. There is no **scoring system** for trace quality, no rubric, no evidence-based evaluation. He relies on vibes and visual inspection. This does not scale and leaves quality control to human attention spans.

### 3.3 Ad-Hoc Memory Governance
While the vault is version-controlled, there is **no structured review gate** before memory changes are applied. The agent writes to the vault; Liu reviews diffs after the fact. There is no concept of pending proposals, approval queues, or rejection. This risks "evergreen threads quietly accumulating vibes."

### 3.4 No Training/Dataset Pipeline
Despite running loops for months, there is no mechanism to export high-quality traces into SFT or DPO datasets. The learning stays inside the thread or inside Codex's proprietary memory layer. The system does not get better over time in a measurable, reproducible way.

### 3.5 Thread-Local, Not System-Local
Heartbeats and memory are thread-local. There is no global policy that says "evaluate all traces daily," "distill failures below score 70," or "export datasets weekly." Each thread is its own island.

### 3.6 Secret Redaction Is Manual
Liu mentions storing the vault as a GitHub repo but does not discuss automated redaction of API keys, tokens, or credentials. This is a liability for any disk-backed memory system.

### 3.7 No Provenance Tracking
When memory is updated or a skill is created, there is no link back to *which trace* produced it, *what evaluation* it passed, or *which version* of the distiller created it. Auditing and rollback are impossible.

---

## 4. What's Missing (Gaps Relative to SkillLoop)

| Missing Capability | Why It Matters | SkillLoop Equivalent |
|-------------------|----------------|----------------------|
| **Deterministic Trace Evaluation** | Without scoring, you cannot distinguish good loops from bad ones automatically. | `eval/rubric.py`, `eval/registry.py` — observable evidence before lexical hints. |
| **Structured Proposal Queue** | Memory changes should be proposals, not direct writes. Humans approve or reject. | `review/queue.py` — `pending` → `approved` → `applied`. |
| **Policy-Driven Governance** | A single config should control ingestion, evaluation, distillation, and export. | `policy.py` — `SkillLoopPolicy` with `IngestionPolicy`, `EvaluationPolicy`, `DatasetPolicy`. |
| **Dataset Export (SFT/DPO)** | High-quality traces should become training data. | `export/sft.py`, `export/dpo.py` — manifest + split generation. |
| **Loop Conditions & Halting** | Prevent infinite loops; stop when score is met or max iterations exceeded. | `conditions.py` — `LoopCondition` with `score_gte`, `max_iterations`, `required_tags`. |
| **Provenance & Auditability** | Every proposal must link to its source trace, evaluation, and distiller version. | `provenance.py` — `annotate_proposal_provenance()`. |
| **Secret Redaction** | Automated sanitization before storage and export. | `sanitize.py` — `redact_secrets()`, `redact_data()`. |
| **Local-First Architecture** | Data lives on the user's machine, not inside a vendor's thread cache. | `store.py` — SQLite/JSONL local store. |
| **Cross-Runtime Adapters** | Ingest traces from Hermes, generic JSONL, or other agents. | `adapters/hermes.py`, `adapters/generic_jsonl.py`. |

---

## 5. What SkillLoop Can Implement (Actionable Takeaways)

### 5.1 Steering Protocol
Capture mid-flight user corrections as **high-priority learning signals**. When a user steers ("make this smaller," "this copy is wrong"), treat that as a `user_correction` tag in evaluation and a strong trigger for memory distillation.

- *Implementation:* Extend `eval/rubric.py` to detect steering language in user messages and boost the learning signal weight.
- *Distillation:* Steering corrections should bypass the score threshold and go straight to proposal generation.

### 5.2 Heartbeat-Style Scheduled Evaluation
SkillLoop already has `LoopSchedule` (hourly/daily/weekly). Codex Heartbeats validate that **recurring, lightweight checks** are a useful primitive.

- *Implementation:* Enhance `loop.py` to support per-trace-type schedules (e.g., evaluate "Chief of Staff" traces every 30 min, coding traces daily).
- *Condition-aware:* Heartbeats should adjust cadence based on condition results (like the Amazon refund example: check every 5 min → switch to every 1 min after response).

### 5.3 Artifact Side Panel for Review
Liu's side panel is the review surface. SkillLoop should support **rendering trace artifacts** during human review.

- *Implementation:* In `review/queue.py`, add artifact preview for Markdown, CSV, HTML, and JSON. HTML traces should render in a sandboxed preview.
- *Annotation:* Allow reviewers to leave comments directly on the artifact, tied to the evaluation record.

### 5.4 Goals with Oracles
A Goal without verification is a wish. SkillLoop's evaluation system should natively support **test-suite oracles**.

- *Implementation:* Extend `eval/evidence.py` with a `test_execution_evidence` extractor that parses `pytest`, `cargo test`, `jest`, etc. A trace that ends with passing tests gets a significant score bonus.
- *Policy:* Add `oracle_command` to `EvaluationPolicy` so users can specify how to verify a goal.

### 5.5 Memory Vault Adapter
Liu's Obsidian vault is a good pattern. SkillLoop should be able to **read from and write to** Git-backed markdown vaults.

- *Implementation:* New adapter `adapters/obsidian_vault.py` that ingests `.md` files as memory context and writes approved proposals back to the vault.
- *Sync:* Treat the vault as a bidirectional memory layer, not just a write target.

### 5.6 Voice Transcript Ingestion
Voice input produces messy, high-context transcripts. SkillLoop should ingest these as first-class traces.

- *Implementation:* Accept audio transcript JSONL as a trace source. Tag messages with `input_mode: voice` so evaluators can weight vague language differently.

### 5.7 Appshot-Style Context Injection
Screenshots and window context are hard to describe but easy to show.

- *Implementation:* Allow traces to carry `image_refs` and `window_context` metadata. The rubric evaluator can note when visual context was present (future: multimodal eval).

### 5.8 Cross-Tool Feedback Loop Evaluation
Liu's animation example (Slack → Remotion → upload) is a **multi-tool trace**. SkillLoop should evaluate these holistically.

- *Implementation:* `eval/rubric.py` should detect multi-tool traces and award bonuses for successful handoffs. A failure in the Slack→Remotion handoff should be scored differently than a failure in a single tool call.

### 5.9 Mobile-Friendly Review Queue
Remote control matters because humans are not always at their desks.

- *Implementation:* A lightweight CLI/HTTP interface for `review/queue.py` that supports approve/reject from mobile. Export pending proposals as a simple web page or Telegram/Slack bot.

### 5.10 HTML as Durable Output
Liu prefers `index.html` over Markdown because it turns output into a small application.

- *Implementation:* In `export/sft.py`, support HTML artifact extraction. In `distill/skills.py`, prefer HTML templates for reusable workflow outputs when the target surface is interactive.

---

## 6. Synthesis

Jason Liu's Codex-maxxing article is a **practitioner's manifesto** for agent operating loops. It validates many of SkillLoop's core assumptions: durable context matters, memory should be inspectable, verification beats ambition, and work should survive between prompts.

However, Codex-maxxing is **artisanal**: it relies on a single vendor, manual review, ad-hoc memory governance, and has no feedback loop into model improvement. SkillLoop is the **industrialized** counterpart: deterministic evaluation, structured proposals, human review gates, policy-driven automation, dataset export, and local-first portability.

The two systems are not competitors; they are **complementary layers**. Codex-maxxing shows what power users want from an agent UX. SkillLoop provides the governance, auditability, and training infrastructure to make those loops safe, scalable, and self-improving.

> **Bottom line:** SkillLoop should steal the UX patterns (steering, heartbeats, side panel, goals with oracles) and replace the governance gaps (deterministic eval, review queues, dataset export, provenance) with its existing architecture.
