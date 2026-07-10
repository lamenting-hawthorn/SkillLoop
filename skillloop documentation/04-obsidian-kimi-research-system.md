# Analysis: Obsidian + Kimi K2.6 Turned My 7,000 Notes Into a $15,000/Month Research System

> **Article:** [Obsidian + Kimi K2.6 turned my 7,000 notes into a $15,000/month research system](https://x.com/noisyb0y1/status/2066856811404087519)  
> **Author:** Noisy (@noisyb0y1)  
> **Date:** June 16, 2026  
> **Analyzed for:** SkillLoop documentation

---

## 1. Article Summary

Noisy's article is a viral X-longform guide describing how to integrate **Obsidian** (a local-first markdown knowledge base) with **Kimi K2.6** (Moonshot AI's 1T-parameter multimodal agentic model) via **MCP** (Model Context Protocol) to create a self-improving research system. The headline claim is that this setup — built on 7,000 existing notes — generates $15,000/month in consulting and product work by making personal knowledge "work while you sleep."

The core thesis is that **most people don't need real RAG**. Noisy explicitly cites Andrej Karpathy's Obsidian-based knowledge system as proof that a clever markdown file structure, a master index, and an LLM with tool access can outperform expensive vector-database setups for sub-million-document corpora. The article positions Obsidian as the "raw folder that catches everything" and Kimi K2.6 as the autonomous research engine that turns that raw material into structured, monetizable output.

### Key Technical Components

| Component | Purpose |
|-----------|---------|
| **Obsidian vault** | Local markdown store; 7,000 notes as the knowledge corpus |
| **MCP integration** | Lets Kimi K2.6 read, edit, and navigate the vault programmatically |
| **SCHEMA.md** | Rules file that instructs K2.6 how to associate concepts, merge duplicates, and record conflicts |
| **Master index** | Navigable entry point so the agent can locate relevant wikis in 1–2 tool calls instead of 50 vector queries |
| **Web Clipper** | Auto-converts any webpage into markdown and drops it into the vault |
| **Reusable Skills** | After a workflow is run once, K2.6 abstracts it into a Skill; subsequent tasks use a single command |
| **Agent Swarm** | Up to 300 parallel sub-agents and 4,000 coordinated steps for complex research deliverables |

### Described Workflow

1. **Ingest:** Web pages, videos, and documents are clipped into the Obsidian vault as markdown.
2. **Structure:** SCHEMA.md rules guide K2.6 to auto-organize notes — linking concepts, merging duplicates, flagging conflicting viewpoints.
3. **Research:** For a client request, K2.6 reads the master index, locates relevant wikis, and either answers directly or spins up an agent swarm for deep analysis.
4. **Deliver:** Output is structured research, strategic analysis, or product specifications — sold as consulting or used to build products.
5. **Evolve:** Successful workflows become reusable Skills; the knowledge base grows more coherent over time.

### Monetization Model

The article claims the system enables:
- **One-off projects** → **Monthly retainers** ($5,000–$10,000/month) for ongoing AI system development and maintenance.
- The operator handles strategy and client relationships; Kimi K2.6 handles the research and synthesis.
- Recurring revenue compounds because the knowledge base improves with every client engagement.

---

## 2. The Good (What Noisy's System Does Well)

### 2.1 Local-First Knowledge Corpus

By using Obsidian as the canonical store, the system keeps the raw knowledge under user control. Notes are plain markdown, portable, and not locked into a SaaS. This aligns with SkillLoop's local-first philosophy and avoids the data-sovereignty risks of cloud-native RAG systems.

### 2.2 Rejection of Over-Engineered RAG

Noisy correctly argues that vector databases, embedding pipelines, and retrieval layers are often unnecessary for personal and small-team knowledge bases. A well-structured folder hierarchy + master index + LLM with file-system tools can cover 90% of use cases. This is a pragmatic, cost-effective stance that SkillLoop should echo in its adapter documentation: sometimes the best retrieval is deterministic file listing, not semantic search.

### 2.3 Self-Improving Schema (SCHEMA.md)

The SCHEMA.md concept is powerful: a human-readable, versionable rules file that tells the agent how to maintain the knowledge base. It encodes conventions like "merge duplicates," "link related concepts," and "record conflicting viewpoints." This is essentially a **policy layer** for knowledge maintenance — analogous to SkillLoop's `policy.json`, but applied to the content layer rather than the learning pipeline.

### 2.4 Skill Abstraction

After running a workflow once (e.g., "process a B-site video into structured notes"), the system abstracts it into a reusable Skill. This is a genuine learning mechanism: the agent captures *how* work is structured and reapplies it. SkillLoop's `distill/` module produces similar skill proposals, but Noisy's system automates the abstraction at the point of execution rather than after trace evaluation.

### 2.5 Multimodal Ingestion

Kimi K2.6's 1T-parameter multimodal capability means video content is processed with both audio transcription *and* visual cue extraction. The resulting notes are richer than audio-only transcripts. For SkillLoop, this highlights the importance of adapter flexibility: traces may soon include vision-tool outputs, and the normalized schema should reserve fields for multimodal artifacts.

### 2.6 Agent Swarm for Complex Deliverables

The article references real examples where K2.6 orchestrates 300 sub-agents across 4,000 steps to produce 40-page research reports with 20,000-entry datasets and 14 figures. This demonstrates that the Obsidian+knowledge base is not just for Q&A — it is the fuel for serious, long-horizon agentic work. SkillLoop's evaluation and dataset export modules should be designed with this scale in mind.

---

## 3. The Bad (What Noisy's System Does Poorly or Risks It Creates)

### 3.1 No Deterministic Evaluation of Output Quality

The article describes a system that *produces* research at scale, but there is no mechanism to *evaluate* whether that research is correct, useful, or hallucinated. A 40-page report with 14 figures sounds impressive, but without rubric-based scoring, human review, or benchmarked accuracy, the $15,000/month claim is unverified. SkillLoop's `eval/` module exists precisely to close this gap.

### 3.2 Automatic Mutation of the Knowledge Base

SCHEMA.md guides K2.6 to "automatically associate concepts, merge duplicate information, and record conflicting viewpoints." This means the agent **writes directly into the canonical knowledge base without review gates**. Risks include:
- **Hallucinated links:** Concepts falsely associated because of surface-level lexical similarity.
- **Destructive merges:** Two genuinely different ideas merged into one because the agent failed to distinguish nuance.
- **Conflict suppression:** The agent may "resolve" conflicts that a human would want preserved.

SkillLoop's `review/` → `apply/` lifecycle prevents exactly this class of failure by requiring human approval before any durable artifact is written.

### 3.3 No Provenance or Replay

If the knowledge base drifts or produces bad output, there is no trace of *which* agent run made *which* change *when*. The SCHEMA.md approach is opaque: the agent decides what to edit, and the edit history is just Obsidian's file-system timestamps. SkillLoop's provenance hashing and controller run reports provide an audit trail that Noisy's system lacks.

### 3.4 Vendor Lock-In to Kimi K2.6

The entire workflow is tightly coupled to Kimi K2.6's specific capabilities: 256k context window, multimodal ingestion, Agent Swarm orchestration, Skill abstraction, and MCP tooling. If Moonshot changes pricing, deprecates features, or geopolitical restrictions apply, the system collapses. There is no runtime-agnostic layer. SkillLoop's adapter architecture is designed to avoid this trap.

### 3.5 No Dataset Export or Model Improvement Pipeline

Despite running thousands of agent steps and producing high-value research, there is no mechanism to turn those traces into SFT/DPO datasets, generate training configs, or improve the underlying model. The "learning" stays trapped in Obsidian notes and Kimi Skills — neither of which is a portable, versionable training artifact. SkillLoop's `export/` and `training_config.py` modules exist to close this loop.

### 3.6 Unrealistic Monetization Claims

The $15,000/month figure is presented as a direct output of the tool stack, but the article provides no evidence, client names, or methodology. It conflates "having a good knowledge system" with "being able to sell consulting retainers." The causal chain is: good tools → better leverage → *possibly* more revenue. SkillLoop should avoid this kind of marketing in its own documentation and focus on measurable loop-quality metrics.

### 3.7 Context Window Limitations

Kimi K2.6's 256k context window, while large, is smaller than some competitors (e.g., GPT-5.4's 1M tokens). For long-horizon research with 300 agents and 4,000 steps, the article admits that "frequent memory compression" is needed, which can cause early details to be lost. A local-first learning governor like SkillLoop can mitigate this by compressing traces into durable, retrieved memories rather than relying solely on context-window gymnastics.

---

## 4. What's Missing (Gaps Neither System Fully Addresses)

### 4.1 Cross-Session Memory for the *Agent*, Not Just the *Vault*

Noisy's system improves the *vault* over time, but Kimi K2.6 itself starts fresh each session. There is no persistent agent memory of "what worked last time" or "what the user corrected." SkillLoop's memory proposals address this, but they are not yet automatically injected into runtime prompts.

### 4.2 Human-in-the-Loop Review at Scale

When 300 agents run 4,000 steps, human review of every action is impossible. But *some* review is necessary — especially for claims that go into client deliverables. Neither Noisy's system nor SkillLoop v1 fully solves "review at swarm scale." A future SkillLoop module could prioritize high-uncertainty steps for human audit.

### 4.3 Stale Knowledge Detection

Obsidian notes age. A SCHEMA.md rule may correctly link two concepts in 2026, but by 2027 one concept may be obsolete. Neither system has an automated "staleness detector" that flags outdated memories or skills for re-evaluation.

### 4.4 Multi-User Scope

Noisy's system is single-user. SkillLoop's current design is also single-tenant. For agency or team use cases, both systems would need user-level, project-level, and global scope separation — similar to Mem0's scoped memory, but with review gates.

---

## 5. What SkillLoop Can Implement

### 5.1 Vault-Aware Adapter (`hermes_obsidian`)

Build an adapter that reads Obsidian vault structures (folders, links, backlinks, tags) as part of trace ingestion. This would let SkillLoop evaluate not just the agent's reasoning, but whether it navigated the vault correctly — e.g., did it check the master index before diving into sub-wikis?

### 5.2 SCHEMA.md Policy Import

Allow users to point SkillLoop at a SCHEMA.md file and derive evaluation rubrics from it. If SCHEMA.md says "merge duplicates," the evaluator can score whether the agent actually identified duplicates or created redundant notes. This bridges Noisy's content-policy layer with SkillLoop's evaluation layer.

### 5.3 Skill Proposal → Review Queue

When Kimi K2.6 (or any runtime) abstracts a workflow into a Skill, SkillLoop should ingest that Skill as a `Proposal` and route it through the review queue. Approved Skills can be exported to `.skillloop/approved/skills/` with full provenance. This gives Noisy's automatic Skill abstraction the governance layer it lacks.

### 5.4 Deterministic Quality Gates for Research Output

Before any trace is allowed to contribute to a dataset or training run, require that research-output traces pass a rubric like:
- Citation coverage (did the agent reference source notes?)
- Conflict acknowledgment (did it flag contradictory sources?)
- Hallucination signals (did it invent facts not present in the vault?)

This would make the $15,000/month claim *verifiable* rather than anecdotal.

### 5.5 Local Skill Registry

Maintain a `.skillloop/skills/` directory that mirrors Kimi's Skill concept but is runtime-agnostic. Each Skill is a markdown file with YAML frontmatter (name, trigger conditions, expected inputs/outputs, provenance). Hermes, Kimi, or any other runtime can read and execute them. This reduces vendor lock-in.

### 5.6 Controller Tick for Knowledge Maintenance

Extend `controller_tick()` to include a "vault health" pass:
- Scan for orphaned notes (no incoming links, no master-index entry).
- Detect duplicate titles or near-duplicate content.
- Flag notes that haven't been updated in N days.
- Propose SCHEMA.md updates based on new content patterns.

This automates the "self-evolving wiki" concept with deterministic evaluation before any write.

### 5.7 Export Research Traces as DPO Pairs

When a research trace is approved, export it as DPO data:
- **Chosen:** The agent's final research output (verified against sources).
- **Rejected:** An earlier draft that missed sources, hallucinated, or failed to flag conflicts.

This turns Noisy's consulting workflow into genuine training data for model improvement.

---

## 6. Summary Table

| Dimension | Noisy's Obsidian + Kimi K2.6 | SkillLoop (Current) | Ideal Hybrid |
|-----------|------------------------------|---------------------|--------------|
| **Knowledge store** | Obsidian (local markdown) | SQLite + `.skillloop/` | Obsidian vault + SQLite metadata |
| **Retrieval** | File-system + master index | Trace store queries | Vault-aware adapters + index |
| **Self-improvement** | SCHEMA.md + Skills (auto-applied) | Proposals + review queue | SCHEMA-derived rubrics + reviewed apply |
| **Evaluation** | None | Deterministic trace scoring | Deterministic + LLM-judge research quality |
| **Provenance** | File timestamps only | Full hash + report trail | Vault edit history + controller reports |
| **Dataset export** | None | SFT/DPO JSONL + manifests | Research-grade DPO from verified traces |
| **Runtime coupling** | Tight (Kimi K2.6 only) | Agnostic (adapters) | Agnostic with runtime-specific optimizations |
| **Human review** | None for vault edits | Required before apply | Prioritized review for high-stakes edits |
| **Multimodal support** | Native (K2.6 vision/audio) | Text traces only | Multimodal trace schema + adapters |
| **Monetization claim** | $15k/month (unverified) | N/A (infrastructure) | Measurable ROI via quality metrics |

---

*SkillLoop should treat Noisy's article as a popular, pragmatic expression of what users want: local knowledge, autonomous research, and reusable skills. The job of SkillLoop is to add the governance, evaluation, and export layers that make that aspiration safe, verifiable, and portable.*
