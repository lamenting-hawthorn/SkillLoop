# Agendex Claims-Grade Evidence Loop Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Evolve SkillLoop from a learning sidecar into an action-centric evidence/governance loop that records who/what agent acted, through which identity, with which permissions and controls, against which data, producing which business outcome.

**Architecture:** Keep SkillLoop's existing trace -> evaluation -> proposal -> review -> export pipeline, but add an Agendex action-event spine between raw traces and evaluations. `AgentTrace` remains the raw/session-level ingestion object; `AgendexActionEvent` becomes the normalized unit for consequential tool/action spans. Detectors evaluate action events into findings/remediation proposals; learning artifacts and datasets become downstream consumers of verified action evidence.

**Tech Stack:** Python dataclasses, SQLite project-local SkillLoop store, existing Hermes `state.db` read-only ingestion, deterministic detector registry, JSONL dataset export, future Postgres integration with `/Users/raghav/agent_architecture` event/audit tables.

---

## 0. Product Direction

SkillLoop should stop positioning itself primarily as a generic “learning loop.” The stronger system is:

```text
raw runtime traces
  -> normalized Agendex action events
  -> deterministic detectors
  -> control findings / remediation proposals
  -> review-gated policy/tool/memory/dataset exports
```

A normal span says:

```text
service A called service B
```

An Agendex span says:

```text
agent X used identity Y to call tool Z with permission P,
under control state C, producing business outcome O
```

The product claim should be:

```text
SkillLoop/Agendex turns agent traces into claims-grade action evidence:
who acted, through which identity, with what permissions and controls,
against what data, producing what business effect — then detects control
and evidence gaps before those actions become institutional memory or
training data.
```

Important wording boundary:

- Early version: “evidence-oriented action tracing with detector findings.”
- Later version, after runtime instrumentation: “claims-grade evidence loop.”

Do not claim “claims-grade” until approval, identity, permission, rollback, audit, and outcome evidence are observed rather than guessed.

---

## 1. Current SkillLoop Baseline

Existing useful pieces:

- `skillloop/schema.py` has `ToolCall`, `AgentTrace`, `Evaluation`, and `Proposal`.
- `skillloop/eval/rubric.py` has deterministic trace scoring.
- `skillloop/eval/evidence.py` extracts command/test/file/user-feedback evidence.
- `skillloop/controller.py` runs `ingest -> evaluate -> distill -> export -> report`.
- `docs/trace-schema.md` already describes `ToolCall` as span-ready.
- `/Users/raghav/agent_architecture/init_schema.sql` already has `event_store.events`, `memory.trace_events`, `memory.audit_log`, and `memory.diagnostic_reports`.

Existing limitations:

- Current traces are message/session-centric.
- Tool calls do not yet carry identity, permission, control, data, and business outcome state.
- Current evals score task quality more than governance/control integrity.
- Memory/skill proposals are first-class, while control findings are missing.
- Old Hermes traces cannot prove every Agendex field; many fields must start as `unknown` or `inferred`.

---

## 2. Canonical Agendex Action Event

Target event shape:

```json
{
  "trace_id": "t_123",
  "span_id": "s_456",
  "parent_span_id": null,
  "agent_id": "claims_resolution_agent",
  "deployment_id": "prod_us_claims_v4",
  "business_workflow": "claim settlement",
  "user_intent": "resolve pending customer claim",
  "agent_plan_step": "approve payout",
  "tool_name": "approve_claim_payout",
  "tool_type": "external_write",
  "tool_criticality": "high",
  "runtime_identity": "svc-agent-claims-prod",
  "permission_granted": ["claims.read", "claims.write", "payments.initiate"],
  "permission_required": ["claims.write"],
  "permission_breadth": "over_scoped",
  "control_state": {
    "human_approval_required": true,
    "human_approval_observed": false,
    "policy_check_observed": true,
    "rate_limit_present": true,
    "rollback_available": false,
    "audit_log_complete": true
  },
  "data_state": {
    "pii_accessed": true,
    "financial_data_accessed": true,
    "cross_tenant_data": false
  },
  "outcome": {
    "external_effect": true,
    "customer_impact": true,
    "financial_impact_possible": true,
    "irreversible": true
  },
  "evidence": {
    "raw_trace_hash": "sha256...",
    "schema_version": "agendex_action_event_v0.1",
    "detector_version": "approval_gap_detector_v0.3"
  }
}
```

Required modeling rule:

Every sensitive governance field must support:

- `observed_true`
- `observed_false`
- `inferred_true`
- `inferred_false`
- `unknown`
- `not_applicable`

Reason: a missing approval event is not the same as proof that approval did not happen. Claims-grade evidence requires the system to distinguish “not observed in monitored evidence” from “observed absent.”

Recommended internal representation:

```python
EvidenceState = Literal[
    "observed_true",
    "observed_false",
    "inferred_true",
    "inferred_false",
    "unknown",
    "not_applicable",
]
```

---

## 3. Implementation Tasks

### Task 1: Add Agendex schema dataclasses

**Objective:** Introduce action-centric schema objects without breaking existing `AgentTrace` ingestion.

**Files:**
- Create: `skillloop/agendex/__init__.py`
- Create: `skillloop/agendex/schema.py`
- Create: `tests/test_agendex_schema.py`
- Modify: `docs/trace-schema.md`

**Steps:**

1. Create `AgendexActionEvent` dataclass.
2. Add nested dataclasses/dicts for `ControlState`, `DataState`, `OutcomeState`, and `EvidenceRef`.
3. Add stable `to_dict()` / `from_dict()` methods.
4. Add SHA-256 canonical hash support like `AgentTrace.compute_normalized_sha256()`.
5. Add validation that `trace_id`, `span_id`, `tool_name`, and `schema_version` are present.
6. Add tests for round-trip serialization, default unknown states, and stable hashing.

**Verification:**

```bash
pytest tests/test_agendex_schema.py -v
```

Expected: all tests pass.

---

### Task 2: Add a tool registry

**Objective:** Define static/default metadata for known tools so Agendex events can classify tool type, criticality, required permissions, data classes, approval policy, and rollback support.

**Files:**
- Create: `skillloop/agendex/tool_registry.py`
- Create: `tests/test_agendex_tool_registry.py`

**Registry fields:**

```python
ToolMetadata(
    tool_name="approve_claim_payout",
    tool_type="external_write",
    criticality="high",
    permission_required=["claims.write"],
    data_classes=["pii", "financial"],
    approval_required=True,
    rollback_available=False,
)
```

**Initial tool type enum:**

- `read_only`
- `internal_write`
- `external_write`
- `code_execution`
- `file_write`
- `network_call`
- `messaging`
- `unknown`

**Verification:**

```bash
pytest tests/test_agendex_tool_registry.py -v
```

Expected: unknown tools return conservative defaults: `tool_type="unknown"`, `criticality="unknown"`, permissions empty, control state unknown.

---

### Task 3: Extract Agendex action events from existing `AgentTrace`

**Objective:** Convert span-ready `ToolCall` objects into normalized Agendex action events using best-effort evidence and explicit unknowns.

**Files:**
- Create: `skillloop/agendex/extract.py`
- Create: `tests/test_agendex_extract.py`
- Modify: `skillloop/adapters/hermes.py` only if needed for metadata preservation

**Extraction rules:**

- One `ToolCall` becomes one `AgendexActionEvent`.
- `trace_id` comes from `AgentTrace.id`.
- `span_id` comes from `ToolCall.id`.
- `tool_name` comes from `ToolCall.name`.
- `agent_id`, `deployment_id`, `business_workflow`, `user_intent`, and `agent_plan_step` come from trace/message metadata when available; otherwise `unknown`.
- `runtime_identity` comes from trace runtime/adapter metadata when available; otherwise `unknown`.
- `permission_required`, `tool_type`, `tool_criticality`, approval policy, data classes, and rollback support come from `tool_registry`.
- `permission_granted` is `unknown` unless runtime instrumentation provides it.
- `evidence.raw_trace_hash` uses `AgentTrace.raw_trace_sha256` or `normalized_trace_sha256`.

**Verification:**

```bash
pytest tests/test_agendex_extract.py -v
```

Expected: extraction never fabricates observed control evidence from missing metadata.

---

### Task 4: Persist Agendex action events in SkillLoop SQLite

**Objective:** Add action-event persistence beside traces/evaluations/proposals.

**Files:**
- Modify: `skillloop/store.py`
- Create: `tests/test_agendex_store.py`

**SQLite table:**

```sql
CREATE TABLE IF NOT EXISTS agendex_action_events (
    id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    span_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    tool_type TEXT NOT NULL,
    tool_criticality TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload TEXT NOT NULL
)
```

**Store methods:**

- `save_action_event(event: AgendexActionEvent) -> str`
- `list_action_events(trace_id: str | None = None) -> list[AgendexActionEvent]`
- `get_action_event(event_id_or_span_id: str) -> AgendexActionEvent`

**Verification:**

```bash
pytest tests/test_agendex_store.py -v
```

Expected: events survive save/load round trip and can be filtered by trace.

---

### Task 5: Add detector registry

**Objective:** Evaluate Agendex action events into deterministic findings.

**Files:**
- Create: `skillloop/agendex/detectors.py`
- Create: `tests/test_agendex_detectors.py`

**Initial detectors:**

1. `approval_gap_detector`
   - high-criticality or external write
   - approval required
   - approval not observed or unknown

2. `over_scoped_permission_detector`
   - granted permissions strictly exceed required permissions

3. `irreversible_external_effect_detector`
   - external effect true
   - irreversible true
   - rollback unavailable or unknown

4. `sensitive_data_action_detector`
   - PII/financial access
   - customer impact or external effect

5. `audit_gap_detector`
   - audit log incomplete or unknown on consequential action

6. `policy_check_gap_detector`
   - policy check absent/unknown on high-criticality action

**Finding fields:**

```python
AgendexFinding(
    id="...",
    action_event_id="...",
    trace_id="...",
    span_id="...",
    detector_name="approval_gap_detector",
    detector_version="0.1",
    severity="high",
    confidence="observed|inferred|unknown_sensitive",
    title="Human approval required but not observed",
    rationale="...",
    evidence_refs=[...],
    recommended_remediation="...",
)
```

**Verification:**

```bash
pytest tests/test_agendex_detectors.py -v
```

Expected: canonical sample event produces an approval-gap finding, over-scope finding, and irreversible-action finding.

---

### Task 6: Expand proposals beyond memory/skill

**Objective:** Let the existing review queue handle governance/control remediation, not just learning artifacts.

**Files:**
- Modify: `skillloop/schema.py`
- Modify: `skillloop/review/queue.py` if kind filtering assumes only memory/skill
- Modify: `skillloop/apply/filesystem.py`
- Create: `tests/test_agendex_finding_proposals.py`

**New proposal kinds:**

- `control_finding`
- `policy_change`
- `tool_registry_update`
- `identity_scope_change`
- `approval_gate`
- `rollback_requirement`
- `dataset_label`

**Rule:** Detector findings create proposals, not direct mutations.

**Verification:**

```bash
pytest tests/test_agendex_finding_proposals.py -v
```

Expected: findings appear as pending review items and can be approved/rejected without writing to global Hermes state.

---

### Task 7: Wire Agendex into controller tick

**Objective:** Extend controller pipeline from trace-level evaluation to action-event extraction and detector evaluation.

**Files:**
- Modify: `skillloop/controller.py`
- Modify: `skillloop/policy.py`
- Create: `tests/test_agendex_controller.py`

**New controller pipeline:**

```text
ingest traces
  -> extract action events
  -> run Agendex detectors
  -> save findings/proposals
  -> existing trace evaluation/distillation
  -> optional dataset export
  -> report
```

**Policy shape:**

```json
{
  "agendex": {
    "enabled": true,
    "extract_action_events": true,
    "detectors": [
      "approval_gap_detector",
      "over_scoped_permission_detector",
      "irreversible_external_effect_detector",
      "sensitive_data_action_detector",
      "audit_gap_detector",
      "policy_check_gap_detector"
    ],
    "create_review_proposals": true
  }
}
```

**Verification:**

```bash
pytest tests/test_agendex_controller.py -v
pytest tests/test_controller.py -v
```

Expected: existing controller behavior remains backward compatible when `agendex.enabled=false`.

---

### Task 8: Add CLI commands

**Objective:** Make Agendex observable and usable from the SkillLoop CLI.

**Files:**
- Modify: `skillloop/cli.py`
- Modify: `docs/cli.md`
- Create: `tests/test_agendex_cli.py`

**Commands:**

```bash
skillloop agendex extract --trace <trace-id>
skillloop agendex events list [--trace <trace-id>]
skillloop agendex events show <event-id-or-prefix>
skillloop agendex detectors run [--trace <trace-id>] [--event <event-id>]
skillloop agendex findings list [--severity high]
skillloop agendex findings show <finding-id-or-prefix>
```

**Verification:**

```bash
pytest tests/test_agendex_cli.py -v
```

Expected: CLI output is clean and does not print secrets or full raw tool arguments by default.

---

### Task 9: Add Agendex dataset export

**Objective:** Export labeled governance evidence for detector benchmarking and future model training.

**Files:**
- Create: `skillloop/export/agendex.py`
- Modify: `skillloop/dataset.py`
- Modify: `skillloop/controller.py`
- Create: `tests/test_agendex_export.py`

**JSONL record shape:**

```json
{
  "action_event": { "...": "..." },
  "findings": [ { "detector_name": "approval_gap_detector", "severity": "high" } ],
  "labels": {
    "approval_gap": true,
    "over_scoped": true,
    "rollback_gap": true,
    "audit_gap": false
  },
  "metadata": {
    "trace_id": "...",
    "span_id": "...",
    "schema_version": "agendex_action_event_v0.1"
  }
}
```

**Verification:**

```bash
pytest tests/test_agendex_export.py -v
```

Expected: export validates JSONL shape and manifest includes action event IDs, detector names/versions, and source trace hashes.

---

### Task 10: Add docs and examples

**Objective:** Document the pivot so future work does not drift back to generic learning-loop language.

**Files:**
- Create: `docs/agendex.md`
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/trace-schema.md`
- Modify: `docs/safety.md`
- Modify: `docs/HANDOFF.md`

**Docs must say:**

- SkillLoop remains the local governor/sidecar.
- Hermes remains the runtime/source of truth.
- Agendex action events are action-centric, not message-centric.
- Unknown/inferred/observed distinctions are mandatory.
- Detector findings are review-gated.
- No direct mutation of Hermes memory/skills/config.
- “Claims-grade” is a target state, not an immediate claim until runtime evidence sources exist.

**Verification:**

```bash
pytest -q
python -m compileall skillloop
```

Expected: tests pass and docs reflect the new architecture.

---

### Task 11: Integrate with local Postgres architecture later

**Objective:** Connect Agendex with `/Users/raghav/agent_architecture` without making SkillLoop’s SQLite the canonical memory database.

**Files:**
- Future create: `skillloop/agendex/postgres.py`
- Future modify: `/Users/raghav/agent_architecture/init_schema.sql` only in that project, not silently from SkillLoop

**Target database placement:**

Use either:

```text
event_store.events(event_type='agent_action')
```

or a dedicated table:

```text
agendex.action_events
agendex.findings
```

Do not store action events as `memory.typed_memory`. Typed memory remains semantic/episodic/procedural memory.

**Mode progression:**

```text
disabled -> read_only -> approved_writes_only
```

**Verification:**

- Read-only mode can query existing event/audit tables.
- Approved-write mode requires explicit apply/review approval.
- `DATABASE_URL` is referenced by environment variable only; never persisted in SkillLoop policy.

---

## 4. Migration Strategy

Do not rewrite everything at once.

Recommended sequence:

1. Add schema and tests.
2. Add tool registry.
3. Add extraction from current `ToolCall`.
4. Persist action events.
5. Add detectors and findings.
6. Expand proposals.
7. Wire controller.
8. Add CLI.
9. Add dataset export.
10. Update docs.
11. Only then add deeper runtime instrumentation.

Backward compatibility rules:

- Existing `AgentTrace` ingestion must keep working.
- Existing SFT/DPO exports must keep working.
- Existing controller policy must keep working when Agendex is disabled.
- Missing Agendex fields must become `unknown`, not fabricated evidence.
- Findings must not auto-apply remediations.

---

## 5. Acceptance Criteria

The Agendex pivot is minimally complete when:

- A trace with tool calls can produce one or more `AgendexActionEvent` records.
- Events persist in `.skillloop/skillloop.db` and can be listed/shown from CLI.
- Canonical high-risk event produces deterministic findings.
- Findings create reviewable proposals.
- Approved findings export locally, not into global Hermes state.
- Dataset export can write governance JSONL with detector labels and manifests.
- Docs clearly describe action-centric evidence vs generic learning.
- Full test suite passes.

Claims-grade readiness requires additional evidence sources:

- observed runtime identity
- observed permission grant source
- observed human approval events
- observed policy check events
- observed audit events
- observed rollback capability
- observed business outcome callback

Until those exist, report detector confidence honestly as observed/inferred/unknown.

---

## 6. Final Verification Command Set

Run after the full implementation:

```bash
pytest -q
python -m compileall skillloop
skillloop status
skillloop controller run
skillloop agendex events list
skillloop agendex findings list
```

Expected:

- tests pass
- compile succeeds
- controller run includes Agendex actions when enabled
- event/finding CLI commands work
- no secrets or private raw traces are printed by default

---

## 7. Suggested Commit Slices

1. `feat: add agendex action event schema`
2. `feat: add agendex tool registry and extraction`
3. `feat: persist agendex action events`
4. `feat: add agendex detector registry`
5. `feat: create reviewable control findings`
6. `feat: wire agendex into controller`
7. `feat: add agendex cli commands`
8. `feat: export agendex governance datasets`
9. `docs: document agendex evidence loop`

Do not commit generated datasets or local `.skillloop/` state.
