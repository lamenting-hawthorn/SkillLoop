# Analysis: Building Recursive Agent Systems (Cursor)

> **Article:** [Building recursive agent systems](https://x.com/leerob/article/2065469795529588940)  
> **Author:** Lee Robinson (Cursor)  
> **Date:** June 12, 2026  
> **Analyzed for:** SkillLoop documentation

---

## 1. Article Summary

Lee Robinson describes how Cursor scales ML training for Composer using a **recursive, always-running agent system** composed of thousands of parallel agents organized into a human → agent "org chart."

The system was born from a scaling pain point: researchers wanted to run thousands more experiments, but tracking status and keeping experiments healthy was slow and manual. Cursor's solution is a **fleet manager** — a main agent running on a massive remote machine that orchestrates hundreds of child agents across many machines.

**How the loop works:**

1. The main agent runs on a remote machine with local dev tools plus a file on disk acting as an **"inbox"** for fleet status.
2. It **SSHes into child-agent machines** and collects their statuses into the inbox.
3. On every loop tick, it **checks fleet health**, keeps healthy tasks running, and **surfaces broken tasks to the team on Slack**.
4. When agents hit transient issues, the main agent can **control the whole fleet** — quitting or restarting processes as needed.
5. The fleet manager has been given **many different skills** encoding tacit knowledge for running ML experiments, reviewing results, and monitoring.
6. If child agents aren't succeeding or run into issues they can't resolve, they **DM the team on Slack or page via PagerDuty**.

The article frames this as a way to scale researcher leverage by orders of magnitude — like having a human manager with 10,000 direct reports, except it actually works. The closing criterion for considering such a system: *"If you have a problem that is verifiable, where throwing more tokens at it will solve it faster or better, it's worth considering building a system like this."*

---

## 2. The Good (What Cursor's System Does Well)

### 2.1 Explicit Loop Architecture
Cursor calls the system what it is: **"an always-running agent system (yes, it's a loop)."** This honesty is refreshing. Rather than dressing up the architecture as emergent or self-organizing, they describe a concrete control loop with a main agent, an inbox, and periodic health checks. SkillLoop shares this philosophy — the loop is a first-class engineering concern, not an implementation detail.

### 2.2 Fleet Health as a Core Responsibility
The main agent's primary job is not dispatching tasks and forgetting them; it is **continuously monitoring and maintaining fleet health**. This elevates the orchestrator from a simple job scheduler to a true control system. SkillLoop's `controller.py` and `conditions.py` embody a similar ethos: evaluation and state checks happen on every tick, not just at submission time.

### 2.3 Human Escalation Boundaries
When agents fail, they do not silently loop or hallucinate recovery. They **DM humans on Slack or page via PagerDuty**. This creates a clean failure mode: the system knows when it is stuck and escalates. SkillLoop's review queue and `conditions.py` stopping rules serve a similar purpose — when evaluation fails or evidence is insufficient, the pipeline stops for human inspection rather than auto-applying.

### 2.4 Skills as Tacit Knowledge Encoders
Cursor encodes operational knowledge (how to run ML experiments, review results, monitor infra) into **skills given to the fleet manager**. This is a practical recognition that agent behavior improves when it is shaped by domain expertise, not just prompt engineering. SkillLoop's `distill/skills.py` and approved skill exports under `.skillloop/approved/skill/` exist to capture and version exactly this kind of knowledge.

### 2.5 Verifiability as a Selection Criterion
The article explicitly limits the domain to problems that are **verifiable** and where more tokens improve outcomes. This is a disciplined scope boundary. Not every problem should be solved with recursive agents. SkillLoop's deterministic `eval/` layer and evidence model provide the verifiability infrastructure that makes such scope decisions data-driven rather than faith-based.

### 2.6 Compute Parallelism Without Human Bottlenecks
By rolling out the infra to everyone in ML, Cursor decouples researcher time from experiment throughput. The scarcest resource (human attention) is protected while the abundant resource (cloud compute) is fully utilized. SkillLoop's local-first, automated controller ticks and dataset export aim for the same leverage: let the machine do the rote work of evaluation, distillation, and data preparation while humans focus on review and high-level decisions.

---

## 3. The Bad (What Cursor's System Does Poorly or Risks It Creates)

### 3.1 No Review Gate Between Agent Output and System Mutation
Child agents write statuses to the inbox; the main agent reads them and acts. There is **no structured review step** between an agent's observation and the system's response. If a child agent hallucinates a status, misreports an experiment result, or confuses a transient error for a fatal one, the main agent acts on corrupted information. SkillLoop's `review/queue.py` → `apply/` lifecycle exists to prevent exactly this class of failure.

### 3.2 Implicit Trust in Agent-Generated Statuses
The inbox model treats agent statuses as ground truth. There is no **evidence-trust scoring**, no distinction between verified tool outputs and agent claims, and no provenance trail for why a status entry was written. SkillLoop's `eval/evidence.py` and provenance hashing are designed to make this distinction explicit.

### 3.3 Monolithic Main Agent as a Single Point of Failure
The entire fleet depends on one main agent running on "a massive remote machine." If that agent fails, gets stuck, or develops a systematic bug in its health-check logic, the entire fleet loses coordination. There is no discussion of **redundancy, replay, or checkpointing** for the main agent itself. SkillLoop's SQLite-backed store and controller run reports provide durable, replayable state that would help diagnose and recover from such a failure.

### 3.4 No Structured Learning Artifacts for the Agents Themselves
The system runs thousands of agents but does not appear to **distill, version, or review** the skills that encode tacit knowledge. If a skill works poorly, there is no explicit feedback loop to improve it — only human intervention when things break. SkillLoop's `distill/` module and proposal review queue close this gap by making skill improvement a governed, evidence-based process.

### 3.5 No Dataset Export or Model Improvement Pipeline
Despite running massive-scale experiments, there is no mention of turning high-quality traces into **SFT/DPO datasets**, generating training configs, or feeding results back into model improvement. The learning stays trapped in the operational layer. SkillLoop's `export/` and `training_config.py` modules exist to extract value from traces beyond their immediate operational use.

### 3.6 Opaque Failure Classification
Agents that "aren't succeeding" DM humans or page PagerDuty, but the article does not describe how success or failure is **classified, scored, or benchmarked**. Without deterministic evaluation, the same trace might be handled differently on different loops. SkillLoop's deterministic `eval/rubric.py` and benchmark replay provide consistent, versioned scoring.

### 3.7 Vendor-Specific Infrastructure Lock-In
The system is deeply tied to Cursor's internal infrastructure (SSH fleet, Slack, PagerDuty, massive remote machines). While this is appropriate for an internal tool, it offers little guidance for teams without similar infrastructure. SkillLoop's runtime-agnostic adapters and local-first architecture are designed to work without assuming a specific cloud provider, chat platform, or orchestration stack.

---

## 4. What's Missing (Gaps Relative to SkillLoop's Goals or General Production Needs)

| Missing Capability | Why It Matters | SkillLoop Equivalent |
|-------------------|----------------|----------------------|
| **Human Review Gate** | Agent outputs mutate system state without approval. | `review/queue.py` — explicit `pending → approved → applied` lifecycle. |
| **Deterministic Trace Evaluation** | No structured scoring of whether an experiment or agent run succeeded. | `eval/rubric.py` + `eval/registry.py` — observable-signal scoring with evidence. |
| **Evidence-Trust Model** | All agent claims treated equally; no distinction between tool output and hallucination. | `eval/evidence.py` — tracks evidence type and trust level. |
| **Skill Versioning & Improvement** | Skills encode tacit knowledge but have no governed update path. | `distill/skills.py` + review/apply — proposals with provenance and human approval. |
| **Dataset Export for Training** | High-quality traces are not turned into model-improvement data. | `export/sft.py`, `export/dpo.py` — JSONL exports with manifests and splits. |
| **Training Config Generation** | No bridge from experiment results to model fine-tuning. | `training_config.py` — TRL/Unsloth/Axolotl configs with safety metadata. |
| **Provenance & Replay** | No way to reconstruct why the main agent made a fleet decision. | `provenance.py` + SQLite store + controller run reports. |
| **Local-First Option** | Requires massive remote machines and cloud fleet. | Read-only adapters, SQLite store, no cloud dependency. |
| **Benchmark & Regression Testing** | No way to test if a skill or policy change improves fleet behavior. | `benchmark.py` — replay evaluator versions over stored traces. |
| **Controlled Auto-Apply Boundaries** | No discussion of what the main agent is allowed to do automatically vs. what requires human approval. | `policy.py` — conservative controller policy with explicit auto-export gates. |

---

## 5. What SkillLoop Can Implement

### 5.1 Fleet-Manager Skill Template
SkillLoop can define an approved skill template for **agent orchestration and health monitoring** that encodes the patterns Cursor uses:

- Inbox-based status collection
- Periodic health-check loops
- Escalation rules (stop → review → notify)
- Fleet control boundaries (what an agent may restart vs. what requires human approval)

This would make Cursor's tacit knowledge explicit, versioned, and reviewable.

### 5.2 Controller Policy for Recursive Agent Traces
SkillLoop's `controller.py` can be extended with a **recursive-agent policy preset** that:

- Ingests traces from child agents via generic JSONL or a future adapter
- Evaluates each child trace for success/failure using deterministic rubrics
- Distills proposals only from child traces that pass evidence thresholds
- Surfaces failing child traces to the review queue with escalation tags
- Auto-exports SFT datasets from high-quality recursive runs

### 5.3 Escalation Conditions for Agent Swarms
`conditions.py` can add a **swarm-escalation condition set**:

- `max_child_failures` — stop the loop if N children fail in one tick
- `required_fleet_health_ratio` — require X% of child agents to report healthy
- `forbid_tag: escalated` — prevent auto-export if any child trace has an escalation tag

These would let SkillLoop govern recursive systems with the same conservative defaults it uses for single-agent traces.

### 5.4 Evidence Model for Agent-Generated Statuses
`eval/evidence.py` should explicitly support **agent-claim evidence types** with lower default trust than tool outputs:

- `tool_output` — high trust
- `user_correction` — high trust
- `agent_claim` — medium trust (requires corroboration)
- `agent_status_report` — low trust (requires health-check validation)

This would let SkillLoop safely ingest traces from recursive agent systems without treating agent-generated statuses as ground truth.

### 5.5 Benchmark for Fleet Manager Skills
`benchmark.py` can be extended to **replay fleet-manager decision traces** across evaluator versions. If Cursor changes how the main agent classifies "healthy" vs. "broken," SkillLoop can replay historical traces to measure whether the new policy would have caught real failures or introduced false positives.

### 5.6 Training Config Preset for Multi-Agent SFT
`training_config.py` can include a preset for **multi-agent orchestration models** — training configs optimized for agents that need to read statuses, make fleet decisions, and escalate appropriately. This would bridge Cursor's operational insights into actual model-capability improvements.

---

## 6. Conclusion

Cursor's recursive agent system is an impressive operational achievement: it scales researcher leverage by orders of magnitude through parallel agents, continuous health monitoring, and clean human escalation. It demonstrates that recursive loops are not theoretical — they are already running in production at scale.

However, the system described is **operationally mature but governance-immature**. It lacks review gates, deterministic evaluation, evidence trust models, skill versioning, dataset export, and training pipelines. These are not criticisms of a tool that was built for a different purpose; they are **opportunities for SkillLoop to provide the missing governance layer**.

SkillLoop's conservative, local-first, review-before-apply architecture is the natural complement to Cursor's high-throughput recursive runtime. Where Cursor throws tokens and compute at verifiable problems, SkillLoop ensures that the resulting traces are **evaluated, distilled, reviewed, and exported** into durable learning artifacts. Together, the two approaches sketch the full picture of what production recursive agent systems will look like: **fast, parallel, and recursively improving — but also governed, inspectable, and safe.**
