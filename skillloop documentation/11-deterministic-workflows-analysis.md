# Deterministic Workflows Analysis for SkillLoop

**Research Date:** 2026-06-21
**Objective:** Evaluate deterministic workflow approaches as an alternative/complement to self-improving/looping architectures in SkillLoop, and identify specific integration opportunities.

---

## Executive Summary

Self-improving loops and autonomous agent architectures are inherently difficult to govern because the execution path is emergent, not prescribed. Even with SkillLoop's review gates, the loop itself remains a black box of tool calls, memory updates, and plan mutations that are hard to verify before they happen.

**Deterministic workflows offer a fundamentally different approach:** instead of letting the agent decide what to do next, you define a state machine where transitions are explicit, verifiable, and replayable. The agent still uses LLMs within nodes, but the graph structure itself is deterministic and auditable.

**Key Finding:** SkillLoop should not replace its loop architecture with deterministic workflows. Instead, it should **add a deterministic workflow layer** that governs when loops are allowed to run, what they can mutate, and how their outputs are validated before state transitions occur. This creates a "deterministic governor over probabilistic workers" architecture.

---

## 1. Leading Approaches to Deterministic Workflows

### 1.1 LangGraph: State Machine-Based Agent Workflows

**What it is:** LangGraph is a framework for building agent workflows as directed graphs with explicit nodes, edges, and state. It supports:

- **Prompt chaining:** Sequential LLM calls where each step processes the output of the previous
- **Parallelization:** Multiple LLM calls running simultaneously, then aggregating results
- **Routing:** Conditional edges based on structured LLM outputs (e.g., route to "pricing" vs "refunds" vs "returns")
- **Orchestrator-worker:** Dynamic task decomposition with parallel worker execution
- **Evaluator-optimizer:** One LLM generates, another evaluates, loops until criteria met

**Governance features:**
- **Checkpointers:** Persist graph state snapshots at every step. Enables time travel, fault tolerance, and conversation continuity
- **Interrupts:** Pause execution at specific points and wait for human approval before continuing
- **Thread-scoped memory:** Each conversation/thread has isolated state
- **Cross-thread stores:** Long-term memory across conversations

**Code pattern (prompt chaining with gate):**

```python
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

class State(TypedDict):
    topic: str
    joke: str
    improved_joke: str
    final_joke: str

def generate_joke(state: State):
    msg = llm.invoke(f"Write a short joke about {state['topic']}")
    return {"joke": msg.content}

def check_punchline(state: State):
    # Deterministic gate - no LLM involved
    if "?" in state["joke"] or "!" in state["joke"]:
        return "Pass"
    return "Fail"

def improve_joke(state: State):
    msg = llm.invoke(f"Make this joke funnier: {state['joke']}")
    return {"improved_joke": msg.content}

workflow = StateGraph(State)
workflow.add_node("generate_joke", generate_joke)
workflow.add_node("improve_joke", improve_joke)
workflow.add_edge(START, "generate_joke")
workflow.add_conditional_edges(
    "generate_joke", check_punchline, {"Fail": "improve_joke", "Pass": END}
)
workflow.add_edge("improve_joke", END)
chain = workflow.compile()
```

**Key insight for SkillLoop:** The `check_punchline` function is a **deterministic evaluator** that gates progress without using an LLM. SkillLoop already has rubric-based evaluators in `eval/rubric.py` - these could be wired directly into workflow edges as deterministic gates.

---

### 1.2 Temporal.io: Durable Execution

**What it is:** Temporal is a platform for durable execution of workflows. Key properties:

- **Durable Execution:** Once a workflow starts, it executes to completion even if processes crash, networks fail, or infrastructure restarts
- **State Checkpointing:** Workflow state is automatically checkpointed after every activity
- **Deterministic Replay:** Workflows must be deterministic - they are replayed from checkpoints on recovery
- **Human-in-the-loop:** Built-in support for signals (async external input) and queries (read workflow state)
- **Polyglot:** Supports multiple languages (Go, Java, TypeScript, Python, .NET, PHP)

**How it achieves determinism:**
- Workflows are deterministic functions - given the same inputs and event history, they must produce the same outputs
- Side effects (API calls, DB writes) are encapsulated in "Activities" which are executed once and their results recorded
- On recovery, the workflow replays from the beginning, but completed activities return their recorded results instead of re-executing

**Governance model:**
- Workflows are visible in a Web UI showing exact state, history, and pending actions
- Can query workflow state at any time without affecting execution
- Can send signals to workflows for human approval or external events
- Supports child workflows for composition

**Key insight for SkillLoop:** Temporal's "Activity" pattern separates deterministic workflow logic from non-deterministic side effects. SkillLoop could adopt a similar pattern where:
- The **workflow graph** (state transitions, review gates, evaluation checkpoints) is deterministic and auditable
- The **agent loop** (tool calls, LLM generation, plan mutation) runs as an "Activity" that is recorded, evaluated, and replayable

---

### 1.3 Interrupts and Human-in-the-Loop (LangGraph Pattern)

LangGraph's `interrupt()` function provides a clean pattern for governance:

```python
from langgraph.types import interrupt, Command

def approval_node(state: State):
    # Pause execution and surface payload to caller
    is_approved = interrupt({
        "question": "Do you want to proceed with this action?",
        "details": state["action_details"]
    })
    
    # Route based on response
    if is_approved:
        return Command(goto="proceed")
    else:
        return Command(goto="cancel")
```

**How it works:**
1. Graph execution suspends at the exact point where `interrupt()` is called
2. State is saved using the checkpointer
3. The interrupt payload is returned to the caller
4. Graph waits indefinitely until resumed with `Command(resume=...)`
5. On resume, the response becomes the return value of `interrupt()`

**Governance implications:**
- Every critical action can have an explicit approval gate
- The state at the point of interruption is fully inspectable
- Multiple parallel branches can each have their own interrupt
- Can review and edit LLM outputs before they propagate to state

**Key insight for SkillLoop:** This is exactly what SkillLoop's `review/apply` pattern tries to do, but LangGraph makes it a first-class primitive with persistence. SkillLoop should adopt a similar interrupt-based review model where the loop pauses before state mutations and waits for explicit approval.

---

## 2. Comparison: Deterministic Workflows vs. Self-Improving Loops

| Dimension | Deterministic Workflows | Self-Improving Loops |
|-----------|------------------------|---------------------|
| **Execution path** | Predefined graph, explicit edges | Emergent, agent decides next step |
| **Predictability** | High - same input always follows same path | Low - non-deterministic due to temperature, context |
| **Governability** | High - can place review gates at any edge | Low - review happens after the fact |
| **Flexibility** | Low - must define all paths upfront | High - agent adapts to novel situations |
| **Debugging** | Easy - replay from any checkpoint | Hard - must reconstruct context |
| **Audit trail** | Complete - every state transition logged | Partial - only tool calls and outputs logged |
| **Human oversight** | Can pause at any defined point | Hard to intercept mid-loop |
| **Failure recovery** | Automatic replay from checkpoint | Manual, may lose context |
| **Learning** | Must explicitly update graph | Implicit from loop iterations |

**The trade-off:** Deterministic workflows are more governable but less flexible. Self-improving loops are more flexible but less governable.

---

## 3. What SkillLoop Can Implement

### 3.1 Workflow State Machine Layer

Add a `workflow` module to SkillLoop that defines agent execution as a state machine:

```python
# skillloop/workflow/engine.py
from typing import TypedDict, Callable, Literal
from dataclasses import dataclass

class WorkflowState(TypedDict):
    trace_id: str
    current_step: str
    loop_count: int
    last_evaluation: dict
    pending_review: bool
    approved: bool

@dataclass
class Transition:
    from_step: str
    to_step: str
    condition: Callable[[WorkflowState], bool]
    requires_review: bool = False
    
class WorkflowEngine:
    def __init__(self):
        self.transitions: dict[str, list[Transition]] = {}
        self.checkpointer = SQLiteCheckpointer()
    
    def add_transition(self, transition: Transition):
        self.transitions.setdefault(transition.from_step, []).append(transition)
    
    def step(self, state: WorkflowState) -> WorkflowState:
        # Save checkpoint before transition
        self.checkpointer.save(state)
        
        # Find valid transitions
        valid = [t for t in self.transitions.get(state["current_step"], [])
                 if t.condition(state)]
        
        if not valid:
            raise WorkflowError(f"No valid transition from {state['current_step']}")
        
        # If review required, pause
        if valid[0].requires_review:
            return self._pause_for_review(state, valid[0])
        
        # Execute transition
        state["current_step"] = valid[0].to_step
        return state
```

### 3.2 Deterministic Evaluation Gates

Wire SkillLoop's existing `eval/rubric.py` into workflow transitions:

```python
# skillloop/workflow/gates.py
from skillloop.eval.rubric import RubricEvaluator

def evaluation_gate(min_score: float = 0.8):
    """Creates a workflow transition condition that requires
    the last evaluation to meet a minimum score."""
    def condition(state: WorkflowState) -> bool:
        eval_result = state.get("last_evaluation", {})
        return eval_result.get("score", 0) >= min_score
    return condition

# Usage in workflow definition
engine.add_transition(Transition(
    from_step="loop_executed",
    to_step="apply_changes",
    condition=evaluation_gate(min_score=0.9),
    requires_review=True  # Even if score passes, require human review
))

engine.add_transition(Transition(
    from_step="loop_executed",
    to_step="retry_loop",
    condition=lambda s: s.get("last_evaluation", {}).get("score", 0) < 0.9
))
```

### 3.3 Interrupt-Based Review (Integration with Existing Review Queue)

Refactor `review/queue.py` to support workflow interrupts:

```python
# skillloop/workflow/interrupts.py
from skillloop.review.queue import ReviewQueue
from skillloop.schema import ReviewItem

class WorkflowInterrupt:
    def __init__(self, queue: ReviewQueue):
        self.queue = queue
        self.pending_interrupts: dict[str, ReviewItem] = {}
    
    def interrupt_for_approval(self, trace_id: str, payload: dict) -> str:
        """Pause workflow and create review item.
        Returns interrupt ID."""
        item = ReviewItem(
            trace_id=trace_id,
            type="workflow_transition",
            payload=payload,
            status="pending"
        )
        review_id = self.queue.add(item)
        self.pending_interrupts[trace_id] = item
        return review_id
    
    def resume(self, trace_id: str, approved: bool, feedback: str = None):
        """Resume workflow after human decision."""
        item = self.pending_interrupts.get(trace_id)
        if not item:
            raise ValueError(f"No pending interrupt for {trace_id}")
        
        item.status = "approved" if approved else "rejected"
        item.feedback = feedback
        self.queue.update(item)
        
        # Trigger workflow resume
        return WorkflowCommand(resume={"approved": approved, "feedback": feedback})
```

### 3.4 Checkpoint/Replay for Loops

Make each loop iteration a checkpointed "activity" in the workflow:

```python
# skillloop/workflow/checkpoint.py
import hashlib
import json
from datetime import datetime

class LoopCheckpoint:
    def __init__(self, store):
        self.store = store
    
    def save(self, trace_id: str, loop_number: int, 
             inputs: dict, outputs: dict, state: dict):
        """Save a checkpoint of the loop state."""
        checkpoint = {
            "trace_id": trace_id,
            "loop_number": loop_number,
            "timestamp": datetime.utcnow().isoformat(),
            "inputs_hash": hashlib.sha256(
                json.dumps(inputs, sort_keys=True).encode()
            ).hexdigest(),
            "outputs_hash": hashlib.sha256(
                json.dumps(outputs, sort_keys=True).encode()
            ).hexdigest(),
            "state": state
        }
        self.store.save_checkpoint(checkpoint)
        return checkpoint
    
    def replay(self, trace_id: str, from_loop: int):
        """Replay loop from a specific checkpoint."""
        checkpoints = self.store.get_checkpoints(trace_id)
        base = next(c for c in checkpoints if c["loop_number"] == from_loop)
        
        # Re-execute subsequent loops
        for cp in checkpoints:
            if cp["loop_number"] > from_loop:
                # Verify determinism: inputs should match
                current_inputs = self._get_inputs(trace_id, cp["loop_number"])
                expected_hash = hashlib.sha256(
                    json.dumps(current_inputs, sort_keys=True).encode()
                ).hexdigest()
                
                if expected_hash != cp["inputs_hash"]:
                    raise DeterminismError(
                        f"Loop {cp['loop_number']} inputs changed - "
                        "cannot deterministic replay"
                    )
        
        return base["state"]
```

### 3.5 Workflow Definition DSL

Allow users to define agent workflows declaratively:

```yaml
# skillloop.yaml
workflow:
  name: "governed_learning_loop"
  
  states:
    - id: "observe"
      description: "Collect trace data"
      
    - id: "evaluate"
      description: "Run rubric evaluation"
      
    - id: "review_gate"
      description: "Human review checkpoint"
      requires_approval: true
      
    - id: "distill"
      description: "Extract skill from trace"
      
    - id: "apply"
      description: "Apply skill to codebase"
      requires_approval: true
      
    - id: "validate"
      description: "Validate applied changes"
      
    - id: "complete"
      description: "Workflow complete"
  
  transitions:
    - from: "observe"
      to: "evaluate"
      condition: "always"
      
    - from: "evaluate"
      to: "review_gate"
      condition: "score >= 0.7"
      
    - from: "evaluate"
      to: "observe"
      condition: "score < 0.7"
      action: "request_more_data"
      
    - from: "review_gate"
      to: "distill"
      condition: "approved == true"
      
    - from: "review_gate"
      to: "observe"
      condition: "approved == false"
      action: "log_rejection"
      
    - from: "distill"
      to: "apply"
      condition: "always"
      
    - from: "apply"
      to: "validate"
      condition: "approved == true"
      
    - from: "validate"
      to: "complete"
      condition: "validation_passed == true"
      
    - from: "validate"
      to: "distill"
      condition: "validation_passed == false"
      max_retries: 3
```

---

## 4. Integration with Existing SkillLoop Architecture

### 4.1 Where It Fits

```
┌─────────────────────────────────────────────────────────────┐
│                     SkillLoop System                        │
├─────────────────────────────────────────────────────────────┤
│  Workflow Layer (NEW)                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Engine    │  │   Gates     │  │   Interrupts        │  │
│  │  (state     │  │ (rubric-    │  │  (review queue      │  │
│  │  machine)   │  │  based)     │  │   integration)      │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                    │             │
│  ┌──────▼────────────────▼────────────────────▼──────────┐  │
│  │              Controller (existing)                    │  │
│  │         (orchestrates loop + workflow)               │  │
│  └──────┬────────────────┬─────────────────────┬─────────┘  │
│         │                │                     │            │
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────────▼────────┐   │
│  │    Loop     │  │    Eval     │  │      Review       │   │
│  │  (existing) │  │  (existing) │  │    (existing)     │   │
│  │             │  │  rubric.py  │  │    queue.py       │   │
│  └─────────────┘  └─────────────┘  └───────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Store (existing SQLite)                │    │
│  │     (checkpoints, traces, reviews, skills)         │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Minimal Viable Integration

**Phase 1: Workflow Wrapper (1-2 weeks)**
- Wrap the existing `loop.py` in a minimal state machine with 3 states: `observe -> evaluate -> decide`
- Add one deterministic gate: only transition to `apply` if evaluation score >= threshold
- Use existing `review/queue.py` as the interrupt mechanism

**Phase 2: Checkpointing (2-3 weeks)**
- Save loop state before and after each iteration
- Enable replay of loop iterations for debugging
- Add determinism verification (input hashes)

**Phase 3: Declarative Workflows (3-4 weeks)**
- YAML-based workflow definitions
- Multiple workflow templates (learning loop, code review, data extraction)
- Visual workflow graph in CLI output

**Phase 4: Advanced Governance (4-6 weeks)**
- Parallel branches with join gates
- Time-based transitions ("if no review in 24h, escalate")
- Sub-workflows (a workflow can spawn another as a child)

---

## 5. The Good Parts (What Deterministic Workflows Add)

1. **Explicit governance:** Every state transition is defined, not emergent
2. **Auditability:** Complete history of every decision point
3. **Reproducibility:** Same inputs always produce same execution path
4. **Human oversight at any point:** Can place review gates before any transition
5. **Failure isolation:** If a loop fails, only that activity needs retry, not the whole workflow
6. **Composability:** Workflows can call other workflows as sub-graphs
7. **Deterministic evaluation:** Rubric scores gate progress, not just inform it

---

## 6. The Bad Parts (What We Lose or Complicate)

1. **Reduced flexibility:** Agent cannot adapt its strategy mid-execution
2. **Upfront design cost:** Must define all states and transitions
3. **State explosion:** Complex agents need many states
4. **Not truly deterministic:** LLM outputs inside nodes are still stochastic
5. **Migration complexity:** Existing loop-based traces need retroactive workflow assignment
6. **Learning slowdown:** Deterministic workflows don't learn how to improve themselves

---

## 7. The Hybrid Architecture: "Deterministic Governor + Probabilistic Worker"

The optimal approach for SkillLoop is not to choose one or the other, but to combine them:

**The workflow layer is deterministic:**
- Defines when loops can run
- Defines what loops can mutate
- Defines evaluation criteria for loop outputs
- Defines review gates before state changes

**The loop layer is probabilistic:**
- Does the actual tool calling, reasoning, and plan mutation
- Operates within constraints set by the workflow
- Its outputs are evaluated deterministically before they affect workflow state

**Example:**

```
Workflow: "skill_distillation"
  State: observe
    -> Loop runs: collects 10 traces (probabilistic)
    -> Checkpoint saved
  State: evaluate  
    -> Deterministic gate: run rubric evaluation on all 10 traces
    -> If average score < 0.8: transition back to observe
    -> If average score >= 0.8: transition to review_gate
  State: review_gate
    -> Interrupt: human reviews proposed skill
    -> If rejected: transition to observe
    -> If approved: transition to distill
  State: distill
    -> Loop runs: extracts skill from traces (probabilistic)
    -> Checkpoint saved
  State: validate
    -> Deterministic gate: run skill against test suite
    -> If tests fail: transition back to distill (max 3 retries)
    -> If tests pass: transition to apply
  State: apply
    -> Interrupt: human reviews diff
    -> If approved: apply to codebase
    -> Transition to complete
```

---

## 8. What Competitors Are Missing

| Competitor | Has Workflows? | Has Review Gates? | Has Deterministic Eval? | Has Checkpoint/Replay? |
|-----------|---------------|-------------------|------------------------|----------------------|
| LangGraph | Yes | Yes (interrupts) | No | Yes |
| Temporal | Yes | Yes (signals) | No | Yes |
| Mem0 | No | No | No | No |
| Cursor | No | No | No | No |
| Factory 2.0 | Partial | No | No | No |
| Opik | No | No | Partial | No |
| Codex | No | No | No | No |
| iii | No | No | No | No |

**SkillLoop's opportunity:** Be the first system to combine:
1. Deterministic workflow state machines
2. Rubric-based deterministic evaluation gates
3. Interrupt-based human review
4. Checkpoint/replay for agent loops
5. Dataset export for training

---

## 9. Recommended Next Steps

### P0 (This Week)
1. **Prototype workflow wrapper:** Wrap `loop.py` in a 3-state machine
2. **Wire rubric evaluator to gates:** Use `eval/rubric.py` scores as transition conditions
3. **Add one interrupt point:** Pause before `apply` and require explicit approval

### P1 (Next 2 Weeks)
4. **Implement checkpointing:** Save loop state before/after each iteration
5. **Add replay capability:** Can replay a loop from any checkpoint
6. **YAML workflow definitions:** Allow users to define workflows declaratively

### P2 (Next Month)
7. **Parallel branches:** Support multiple evaluators running in parallel
8. **Sub-workflows:** A workflow can call another workflow
9. **Visual workflow graph:** CLI command to render workflow as Mermaid diagram

### P3 (Next Quarter)
10. **Workflow marketplace:** Pre-built workflow templates for common patterns
11. **Workflow provenance:** Track which workflow version produced which skill
12. **Workflow evaluation:** Evaluate workflows themselves using rubrics

---

## 10. Key Papers and References

- **LangGraph Documentation:** https://docs.langchain.com/oss/python/langgraph/workflows-agents
- **LangGraph Persistence:** https://docs.langchain.com/oss/python/langgraph/persistence
- **LangGraph Interrupts:** https://docs.langchain.com/oss/python/langgraph/interrupts
- **Temporal Why Temporal:** https://docs.temporal.io/evaluate/why-temporal
- **Temporal Python SDK:** https://docs.temporal.io/develop/python
- **"Deterministic AI Agents"** - search arxiv for formal methods in agent systems
- **"Structured agent workflows"** - Anthropic's research on workflow patterns

---

## 11. Conclusion

Deterministic workflows are not a replacement for SkillLoop's self-improving loop - they are a governance layer that makes the loop safe to run. By adding a workflow engine with deterministic evaluation gates, checkpoint/replay, and interrupt-based review, SkillLoop can offer something no competitor has: **a governed loop where every iteration is auditable, every transition is justified, and every mutation is approved.**

The 3-6 month competitive window is still open. No competitor combines deterministic workflows with deterministic evaluation and human review. SkillLoop should seize this opportunity.
