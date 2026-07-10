# Plan: goal-loop Executable Skill for ECC

> Document version: 2025-06-21
> Target repo: https://github.com/affaan-m/ECC
> Contribution type: Executable skill (SKILL.md + scripts/ + templates/ + hooks/)
> Based on: SkillLoop's goal-loop reference skill, controller.py, policy.py, fs_safety.py
> Our prior merged PRs: #2220 (agent-self-evaluation), #2235 (tdd-workflow security hardening)

---

## 1. Executive Summary

Build `goal-loop`, an ECC skill that enables autonomous agent loops with a maker-checker split, externalized STATE.md persistence, and a declarative stop-condition DSL. Unlike a passive markdown skill, this contribution includes executable Python scripts that actually manage state, evaluate stop conditions, and orchestrate iterations.

**Why this matters:** ECC is an executable agent harness (50+ scripts, hook dispatchers, CI pipeline). A markdown-only skill is passive text. This contribution ships runnable code.

---

## 2. START HERE — Exact First Steps for the Agent

If you are an agent picking up this plan, do these steps in order. Do not skip.

### Step 0: Prerequisites
- Ensure Python 3.10+ is available
- Ensure `git` is available
- Ensure `node` is available (for ECC validators)

### Step 1: Clone and Branch
```bash
git clone https://github.com/affaan-m/ECC.git ~/ecc
cd ~/ecc
git checkout -b feat/goal-loop-skill
```

### Step 2: Create Directory Structure
```bash
mkdir -p skills/goal-loop/scripts
mkdir -p skills/goal-loop/templates
mkdir -p skills/goal-loop/hooks
mkdir -p skills/goal-loop/tests
```

### Step 3: Verify You Can Run ECC Validators
```bash
cd ~/ecc
node scripts/ci/validate-skills.js
# This should run without error (it validates existing skills)
```

### Step 4: Read This Entire Plan
Read all sections before writing any code. The spec is frozen. Do not change v1 scope.

### Step 5: Start Phase 2
Go to Section 5 (Build Phases). Execute Phase 2 by spawning 3 parallel sub-agents using the pre-filled prompts in Section 14. Do not proceed to Phase 3 until Gate 2 passes.

---

## 2. ECC Repository Context

### 2.1 What ECC Actually Is

ECC (Effective Coding Capabilities) is a production-ready AI coding plugin / agent harness performance system. It is NOT just a prompt library.

- **218k stars, 33.3k forks**
- **67 agents, 271 skills, 92 commands**
- Ships with automated hook workflows
- v1.8.0 release explicitly frames it as "agent harness performance system, not just a config pack"

### 2.2 Repository Structure (Relevant Parts)

```
affaan-m/ECC/
├── skills/                          # Skill definitions
│   ├── skill-comply/               # EXAMPLE: full Python package (9 modules + tests)
│   │   ├── SKILL.md
│   │   ├── pyproject.toml
│   │   └── scripts/
│   │       ├── parser.py
│   │       ├── grader.py
│   │       ├── classifier.py
│   │       ├── runner.py
│   │       └── ...
│   ├── continuous-learning-v2/     # EXAMPLE: hooks + shell scripts + Python CLI
│   │   ├── SKILL.md
│   │   ├── config.json
│   │   ├── agents/
│   │   │   ├── start-observer.sh
│   │   │   └── session-guardian.sh
│   │   ├── hooks/
│   │   │   └── observe.sh
│   │   └── instinct-cli.py
│   ├── agent-self-evaluation/      # EXAMPLE: standalone evaluator (our PR #2220)
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       └── evaluate.py
│   └── ...
├── scripts/                         # Global scripts (50+ executable JS/Python/shell)
│   ├── ci/
│   │   └── validate-skills.js      # CI validator — checks existence + frontmatter only
│   └── ...
├── hooks/                           # Event-triggered automation
├── commands/                        # Slash-entry workflows
├── tests/                           # Test suite (997+ internal tests)
│   ├── run-all.js
│   ├── lib/
│   │   ├── skill-improvement.test.js
│   │   └── skill-evolution.test.js
│   └── ...
├── .github/
│   └── workflows/
│       └── reusable-validate.yml   # Full CI: agents, hooks, commands, skills, rules, security
└── AGENTS.md                        # Defines ECC as "production-ready AI coding plugin"
```

### 2.3 What a "Real" Skill Looks Like in ECC

High-value skills include executable artifacts, not just markdown:

| Skill | What It Ships |
|-------|---------------|
| `skill-comply` | Python package: parser, grader, classifier, runner, tests |
| `continuous-learning-v2` | config.json, shell agents, hooks, Python CLI |
| `agent-self-evaluation` | `scripts/evaluate.py` — scores agent output on 5 axes |
| `videodb` | `scripts/ws_listener.py` — WebSocket listener |
| `rules-distill` | `scripts/scan-rules.sh` — shell scanner |
| `frontend-slides` | `scripts/export-pdf.sh` — PDF export automation |

**Low-value skills:** Just `SKILL.md` with YAML frontmatter. These exist but are treated as inert documentation.

### 2.4 CI Validation

- `scripts/ci/validate-skills.js`: Checks that SKILL.md exists, is non-empty, has `name:` and `description:` frontmatter. **Does NOT test functionality.**
- `tests/run-all.js`: 997+ tests covering agents, hooks, commands, skills, rules, workflow security.
- `tests/lib/skill-improvement.test.js` and `skill-evolution.test.js`: Expect skills to be measurably improvable.

### 2.5 Our Prior Merged PRs

- **PR #2220**: `agent-self-evaluation` skill + `agent-evaluator` persona
  - File: `skills/agent-self-evaluation/scripts/evaluate.py`
  - Behavior: Scores agent output on 5 axes using regex heuristics, produces structured reports
  - **We can reuse/extend this as the checker component of goal-loop**

- **PR #2235**: `tdd-workflow` security hardening
  - Plan handoff injection guards
  - **We should apply the same security mindset to goal-loop (input validation, path safety)**

---

## 3. goal-loop Skill Specification

### 3.1 Objective

Implement an ECC skill that enables autonomous agent loops with:
1. **Maker-checker split**: Worker executes; independent checker evaluates
2. **Externalized STATE.md**: All loop state persisted to a file, enabling resume-not-restart
3. **Declarative stop-condition DSL**: User defines when the loop stops
4. **Command interface**: `/goal-loop start`, `tick`, `status`, `pause`, `resume`, `stop`

### 3.2 File Structure

```
skills/goal-loop/
├── SKILL.md                        # Behavioral spec, command definitions, usage examples
├── scripts/
│   ├── __init__.py
│   ├── goal_loop.py               # Main orchestrator: start, tick, status, pause, resume, stop
│   ├── state_manager.py           # STATE.md read/write, schema validation, resume logic
│   ├── stop_condition.py          # DSL parser + evaluator (score_gte, required_tags, forbidden_tags, max_iterations)
│   ├── checker.py                 # Invokes checker persona (reuses agent-self-evaluation from PR #2220)
│   └── validate.py                # Standalone validation script for STATE.md and stop conditions
├── templates/
│   └── STATE.md                   # Template with Jinja2-style placeholders
├── hooks/
│   └── goal-loop.json             # Optional: PreToolUse/PostToolUse hooks for auto-tick
└── tests/
    ├── test_state_manager.py
    ├── test_stop_condition.py
    └── test_goal_loop.py
```

### 3.3 Command Interface

All commands are slash commands defined in SKILL.md frontmatter. The scripts are invoked by the agent via Bash tool.

| Command | Behavior | Script Entry Point |
|---------|----------|-------------------|
| `/goal-loop start <goal> [--checker <persona>] [--max-iterations N] [--stop-on <condition>]` | Initialize STATE.md with goal, checker, stop condition | `python scripts/goal_loop.py start --goal "..." ...` |
| `/goal-loop tick` | Execute one maker iteration, then checker evaluation, update STATE.md | `python scripts/goal_loop.py tick` |
| `/goal-loop status` | Read STATE.md and report current progress | `python scripts/goal_loop.py status` |
| `/goal-loop pause` | Set status to paused in STATE.md | `python scripts/goal_loop.py pause` |
| `/goal-loop resume` | Set status to running, continue from current_iteration | `python scripts/goal_loop.py resume` |
| `/goal-loop stop` | Set status to completed/aborted, write conclusion | `python scripts/goal_loop.py stop --reason "..."` |

### 3.4 STATE.md Schema

```yaml
goal_loop:
  version: "1.0"
  goal: "string"
  started_at: "ISO8601"
  checker_persona: "string"
  stop_condition:
    score_gte: 80
    required_tags: ["verified"]
    forbidden_tags: ["error", "reverted"]
    max_iterations: 10
  iterations:
    - id: 1
      started_at: "ISO8601"
      finished_at: "ISO8601"
      worker_actions: ["action summaries"]
      checker_score: 85
      checker_tags: ["verified"]
      state: "passed|failed|pending"
  current_iteration: 2
  status: "running|paused|completed|aborted"
  conclusion:
    reason: "max_iterations_reached"
    final_score: 82
```

### 3.5 Stop-Condition DSL

YAML-based, parsed by `stop_condition.py`:

```yaml
score_gte: 80              # minimum evaluator score (optional)
required_tags:             # all must be present (optional)
  - "verified"
forbidden_tags:            # any aborts the loop (optional)
  - "error"
  - "reverted"
max_iterations: 10         # hard cap (optional, default 20)
```

**Evaluation logic:**
1. If `max_iterations` reached → stop, reason: `max_iterations_reached`
2. If latest iteration has any `forbidden_tags` → stop, reason: `forbidden_tag_hit`
3. If latest iteration's `checker_score` >= `score_gte` AND all `required_tags` present → stop, reason: `condition_met`
4. Otherwise → continue

### 3.6 Maker-Checker Protocol

1. **Worker** (default agent persona) executes one task step, writes to working files
2. **Checker** (separate persona, default: `agent-evaluator` from PR #2220) evaluates the step using Read tools only
3. Checker emits: `score` (0-100), `tags[]`, `rationale` (text)
4. `state_manager.py` appends iteration record to STATE.md
5. `stop_condition.py` evaluates whether to stop
6. If not stopped, loop waits for next `/goal-loop tick`

### 3.7 Resume-Not-Restart

- STATE.md is the single source of truth
- On `/goal-loop resume`, `state_manager.py` reads STATE.md, finds `current_iteration`, sets `status: running`
- No session state assumed; all context comes from STATE.md + filesystem
- If STATE.md is missing or corrupt, error with clear message

### 3.8 Integration with PR #2220

- Default checker persona: `agent-evaluator`
- `checker.py` invokes the existing `skills/agent-self-evaluation/scripts/evaluate.py` if available
- If not available, falls back to a built-in lightweight rubric in `checker.py`
- Reuses the same 5-dimension rubric: correctness, completeness, verification, security_hygiene, efficiency

---

## 4. Implementation Details

### 4.1 Clean Code Principles (Mandatory)

Every file must follow these principles:

1. **Single Responsibility**: Each module does one thing.
   - `state_manager.py` → only STATE.md I/O and schema validation
   - `stop_condition.py` → only DSL parsing and evaluation
   - `checker.py` → only checker invocation and result normalization
   - `goal_loop.py` → only orchestration and command dispatch

2. **Clear Naming**: No abbreviations.
   - `checker_score` not `cs`
   - `stop_condition` not `exit_cond`
   - `current_iteration` not `cur_iter`

3. **No Duplication**: Stop-condition DSL reused across start command and status display.
   - One parser class, used by both `goal_loop.py start` and `goal_loop.py status`

4. **Minimal Coupling**: `goal_loop.py` orchestrates but does not know internal details of checker implementation.
   - `checker.py` exposes `evaluate(iteration_actions) -> CheckerResult`
   - `goal_loop.py` only calls that method

5. **Fail Fast**: Input validation at module boundaries.
   - `state_manager.py` validates STATE.md schema on read; raises on corrupt files
   - `stop_condition.py` validates DSL on parse; raises on invalid syntax
   - `goal_loop.py` validates command-line arguments before any state mutation

6. **No Magic Numbers**: All defaults are constants.
   - `DEFAULT_MAX_ITERATIONS = 20`
   - `DEFAULT_SCORE_GTE = 70`
   - `STATE_VERSION = "1.0"`

### 4.2 Module Specifications

#### `scripts/state_manager.py`

```python
"""STATE.md I/O, schema validation, and resume logic."""

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

STATE_VERSION = "1.0"
STATE_FILENAME = "STATE.md"

@dataclass
class IterationRecord:
    id: int
    started_at: str
    finished_at: str
    worker_actions: list[str]
    checker_score: int
    checker_tags: list[str]
    state: str  # "passed", "failed", "pending"

@dataclass
class StopCondition:
    score_gte: Optional[int] = None
    required_tags: list[str] = None
    forbidden_tags: list[str] = None
    max_iterations: int = 20

@dataclass
class GoalLoopState:
    version: str
    goal: str
    started_at: str
    checker_persona: str
    stop_condition: StopCondition
    iterations: list[IterationRecord]
    current_iteration: int
    status: str  # "running", "paused", "completed", "aborted"
    conclusion: Optional[dict[str, Any]] = None

class StateManager:
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root).resolve()
        self.state_path = self.project_root / STATE_FILENAME

    def exists(self) -> bool:
        return self.state_path.exists()

    def load(self) -> GoalLoopState:
        """Load and validate STATE.md. Raise on corrupt/missing."""
        ...

    def save(self, state: GoalLoopState) -> None:
        """Serialize GoalLoopState to STATE.md as YAML frontmatter + markdown body."""
        ...

    def create_initial(self, goal: str, checker_persona: str, stop_condition: StopCondition) -> GoalLoopState:
        """Create new state with defaults."""
        ...

    def append_iteration(self, record: IterationRecord) -> GoalLoopState:
        """Append iteration, increment current_iteration, save."""
        ...

    def set_status(self, status: str) -> GoalLoopState:
        """Update status and save."""
        ...

    def set_conclusion(self, reason: str, final_score: Optional[int] = None) -> GoalLoopState:
        """Write conclusion, set status to completed/aborted, save."""
        ...
```

**Key behaviors:**
- `load()` must validate schema version; reject unknown versions
- `save()` writes YAML frontmatter (between `---` markers) + human-readable markdown body
- `save()` must be atomic: write to temp file, then rename
- All paths resolved under `project_root`; reject paths outside (path traversal prevention)

#### `scripts/stop_condition.py`

```python
"""Stop-condition DSL parser and evaluator."""

from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class StopCondition:
    score_gte: Optional[int] = None
    required_tags: list[str] = None
    forbidden_tags: list[str] = None
    max_iterations: int = 20

    @classmethod
    def from_dict(cls, data: dict) -> "StopCondition":
        """Parse from dict. Validate types and ranges."""
        ...

    @classmethod
    def from_yaml_string(cls, yaml_str: str) -> "StopCondition":
        """Parse from YAML string."""
        ...

    def evaluate(self, iteration_score: int, iteration_tags: list[str], current_iteration: int) -> "StopResult":
        """Evaluate whether loop should stop."""
        ...

@dataclass(frozen=True)
class StopResult:
    should_stop: bool
    reason: Optional[str] = None
```

**Key behaviors:**
- `from_dict()` validates: `score_gte` must be 0-100, `max_iterations` must be >= 1, tags must be list of strings
- `evaluate()` returns `StopResult` with `should_stop` and `reason`
- Evaluation order: max_iterations → forbidden_tags → score_gte + required_tags

#### `scripts/checker.py`

```python
"""Checker invocation and result normalization."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass(frozen=True)
class CheckerResult:
    score: int  # 0-100
    tags: list[str]
    rationale: str

class Checker:
    def __init__(self, persona: str, project_root: Path):
        self.persona = persona
        self.project_root = Path(project_root).resolve()

    def evaluate(self, worker_actions: list[str], context_files: Optional[list[Path]] = None) -> CheckerResult:
        """Invoke checker persona and normalize result."""
        ...

    def _invoke_agent_evaluator(self, worker_actions: list[str]) -> CheckerResult:
        """Try to use PR #2220's agent-self-evaluation script."""
        ...

    def _fallback_rubric(self, worker_actions: list[str]) -> CheckerResult:
        """Built-in lightweight rubric if agent-self-evaluation unavailable."""
        ...
```

**Key behaviors:**
- Primary: Try to invoke `skills/agent-self-evaluation/scripts/evaluate.py` if it exists
- Fallback: Built-in regex-based rubric (lightweight, no external dependencies)
- Never modifies filesystem; read-only evaluation
- Returns normalized `CheckerResult` regardless of checker source

#### `scripts/goal_loop.py`

```python
"""Main orchestrator and CLI entry point."""

import argparse
import sys
from pathlib import Path

from state_manager import StateManager, GoalLoopState, IterationRecord, StopCondition
from stop_condition import StopCondition as StopCond, StopResult
from checker import Checker, CheckerResult

def cmd_start(args):
    """Initialize STATE.md."""
    ...

def cmd_tick(args):
    """Execute one iteration."""
    ...

def cmd_status(args):
    """Report current progress."""
    ...

def cmd_pause(args):
    """Pause loop."""
    ...

def cmd_resume(args):
    """Resume loop."""
    ...

def cmd_stop(args):
    """Finalize loop."""
    ...

def main():
    parser = argparse.ArgumentParser(description="goal-loop orchestrator")
    subparsers = parser.add_subparsers(dest="command")

    start_parser = subparsers.add_parser("start")
    start_parser.add_argument("--goal", required=True)
    start_parser.add_argument("--checker", default="agent-evaluator")
    start_parser.add_argument("--max-iterations", type=int, default=20)
    start_parser.add_argument("--score-gte", type=int)
    start_parser.add_argument("--required-tags", nargs="+", default=[])
    start_parser.add_argument("--forbidden-tags", nargs="+", default=[])
    start_parser.add_argument("--project-root", default=".")

    tick_parser = subparsers.add_parser("tick")
    tick_parser.add_argument("--project-root", default=".")

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--project-root", default=".")

    pause_parser = subparsers.add_parser("pause")
    pause_parser.add_argument("--project-root", default=".")

    resume_parser = subparsers.add_parser("resume")
    resume_parser.add_argument("--project-root", default=".")

    stop_parser = subparsers.add_parser("stop")
    stop_parser.add_argument("--reason", required=True)
    stop_parser.add_argument("--project-root", default=".")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    command_map = {
        "start": cmd_start,
        "tick": cmd_tick,
        "status": cmd_status,
        "pause": cmd_pause,
        "resume": cmd_resume,
        "stop": cmd_stop,
    }

    command_map[args.command](args)

if __name__ == "__main__":
    main()
```

**Key behaviors:**
- Each command is a pure function: reads STATE.md, performs operation, writes STATE.md
- No global state; all state in STATE.md
- `cmd_tick()` is the most complex: loads state, validates status is "running", collects worker actions from user/agent, invokes checker, appends iteration, evaluates stop condition, updates status if stopped
- All commands validate that STATE.md exists before operating (except `start`)

#### `scripts/validate.py`

```python
"""Standalone validation script for STATE.md and stop conditions."""

from pathlib import Path
import sys

from state_manager import StateManager
from stop_condition import StopCondition

def validate_state_file(path: Path) -> bool:
    """Validate a STATE.md file. Print errors to stderr."""
    ...

def validate_stop_condition(yaml_str: str) -> bool:
    """Validate a stop-condition YAML string."""
    ...

def main():
    ...

if __name__ == "__main__":
    main()
```

**Key behaviors:**
- Exit code 0 if valid, 1 if invalid
- Prints specific error messages (e.g., "Invalid schema version: expected 1.0, got 2.0")
- Can be run standalone or invoked by CI

#### `templates/STATE.md`

```markdown
---
goal_loop:
  version: "1.0"
  goal: "{{ goal }}"
  started_at: "{{ started_at }}"
  checker_persona: "{{ checker_persona }}"
  stop_condition:
    score_gte: {{ score_gte }}
    required_tags: {{ required_tags }}
    forbidden_tags: {{ forbidden_tags }}
    max_iterations: {{ max_iterations }}
  iterations: []
  current_iteration: 0
  status: "running"
  conclusion: null
---

# Goal Loop State

**Goal:** {{ goal }}
**Started:** {{ started_at }}
**Status:** running
**Checker:** {{ checker_persona }}

## Stop Condition

- Score >= {{ score_gte }}
- Required tags: {{ required_tags }}
- Forbidden tags: {{ forbidden_tags }}
- Max iterations: {{ max_iterations }}

## Iterations

No iterations yet.
```

**Key behaviors:**
- Jinja2-style placeholders for initial creation
- After creation, `state_manager.py` reads/writes the YAML frontmatter directly
- Markdown body is for human readability; YAML frontmatter is for machine parsing

#### `hooks/goal-loop.json`

```json
{
  "name": "goal-loop-auto-tick",
  "description": "Auto-trigger goal-loop tick after tool use",
  "event": "PostToolUse",
  "match": {
    "tool": "Bash",
    "command": "goal-loop"
  },
  "action": {
    "type": "notify",
    "message": "Goal loop iteration completed. Run /goal-loop status to check progress."
  }
}
```

**Note:** This is optional for v1. The primary interface is slash commands.

### 4.3 SKILL.md Structure

```markdown
---
name: goal-loop
version: "1.0"
description: Autonomous agent loops with maker-checker split, STATE.md persistence, and declarative stop conditions
author: "Your Name"
tags: ["automation", "loop", "evaluation", "state-management"]
commands:
  - name: goal-loop-start
    description: Initialize a new goal loop
    usage: /goal-loop start <goal> [--checker <persona>] [--max-iterations N] [--score-gte N] [--required-tags tag1,tag2] [--forbidden-tags tag1,tag2]
  - name: goal-loop-tick
    description: Execute one iteration of the goal loop
    usage: /goal-loop tick
  - name: goal-loop-status
    description: Show current loop progress
    usage: /goal-loop status
  - name: goal-loop-pause
    description: Pause the loop
    usage: /goal-loop pause
  - name: goal-loop-resume
    description: Resume the loop from current state
    usage: /goal-loop resume
  - name: goal-loop-stop
    description: Stop the loop and write conclusion
    usage: /goal-loop stop --reason "..."
---

# goal-loop

## Overview

`goal-loop` enables autonomous agent loops with a maker-checker architecture. The worker executes task steps; an independent checker evaluates each step against a rubric. Loop state is persisted to `STATE.md`, enabling resume-not-restart semantics.

## Architecture

[Diagram or description of maker-checker flow]

## Commands

### /goal-loop start

... detailed description ...

### /goal-loop tick

... detailed description ...

... etc ...

## Stop-Condition DSL

... syntax and semantics ...

## STATE.md Schema

... full schema documentation ...

## Examples

### Example 1: Bug-fix loop

... step-by-step example ...

### Example 2: Documentation update loop

... step-by-step example ...

## Integration with agent-self-evaluation

... how it uses our PR #2220 ...

## Safety

... path traversal prevention, no global state mutation, review-before-apply ...
```

---

## 5. Build Phases and Deterministic Gates

### Phase 1: SPEC LOCK (0.5 days)

**Activities:**
- Review this plan document
- Approve or modify the spec
- Lock v1 scope (no changes after lock)

**Gate 1: Spec approved by user**
- [ ] User approves this document
- [ ] v1 scope is frozen

---

### Phase 2: CORE MODULES (2 days)

**Activities:**
- Implement `state_manager.py`
- Implement `stop_condition.py`
- Implement `checker.py` (with fallback)
- Implement `validate.py`
- Write unit tests for each module

**Sub-agent workflow:**
- Agent A: Implement `state_manager.py` + tests
- Agent B: Implement `stop_condition.py` + tests
- Agent C: Implement `checker.py` + `validate.py` + tests
- **All agents run in parallel**

**Gate 2: Module tests pass**
- [ ] `python -m pytest tests/test_state_manager.py` passes
- [ ] `python -m pytest tests/test_stop_condition.py` passes
- [ ] `python -m pytest tests/test_checker.py` passes
- [ ] `python scripts/validate.py --state templates/STATE.md` passes

---

### Phase 3: ORCHESTRATOR + TEMPLATE (1 day)

**Activities:**
- Implement `goal_loop.py` CLI
- Create `templates/STATE.md`
- Write integration tests for full command flow

**Sub-agent workflow:**
- Agent D: Implement `goal_loop.py`
- Agent E: Create `templates/STATE.md` + integration tests
- **Agents run in parallel**

**Gate 3: Integration tests pass**
- [ ] `python scripts/goal_loop.py start --goal "test" --score-gte 80` creates valid STATE.md
- [ ] `python scripts/goal_loop.py tick` appends iteration
- [ ] `python scripts/goal_loop.py status` reports correctly
- [ ] `python scripts/goal_loop.py pause` / `resume` toggles status
- [ ] `python scripts/goal_loop.py stop --reason "done"` writes conclusion
- [ ] Resume flow: stop, resume, tick works from saved STATE.md

---

### Phase 4: SKILL.md + HOOKS + POLISH (0.5 days)

**Activities:**
- Write `SKILL.md` with full documentation
- Create `hooks/goal-loop.json` (optional)
- Run ECC validators
- Run Unicode safety scan
- Final code review against Clean Code principles

**Gate 4: Validation passes**
- [ ] `node scripts/ci/validate-skills.js` exits 0 on `skills/goal-loop/`
- [ ] No Unicode safety issues in generated files
- [ ] All functions < 20 lines (Clean Code)
- [ ] No module imports another module's internal classes directly
- [ ] All path operations use `Path.resolve()` and validate under project root

---

### Phase 5: PR PREPARATION (0.5 days)

**Activities:**
- Stage files in clean branch
- Write PR description
- Final diff review
- Push and open PR

**Gate 5: PR ready**
- [ ] All files committed
- [ ] PR description includes: what, why, how, test evidence, scope
- [ ] References PR #2220 and PR #2235 where relevant

---

## 6. Test Strategy

### 6.1 Unit Tests

```python
# tests/test_state_manager.py
# tests/test_stop_condition.py
# tests/test_checker.py
```

Use `pytest` with `tmp_path` fixture for filesystem isolation.

### 6.2 Integration Tests

Simulate full command flow:

```bash
# Test 1: Full loop lifecycle
cd /tmp/test-project
python ~/ecc/skills/goal-loop/scripts/goal_loop.py start --goal "Fix bug #123" --score-gte 80 --max-iterations 3
python ~/ecc/skills/goal-loop/scripts/goal_loop.py tick  # iteration 1
python ~/ecc/skills/goal-loop/scripts/goal_loop.py status
python ~/ecc/skills/goal-loop/scripts/goal_loop.py pause
python ~/ecc/skills/goal-loop/scripts/goal_loop.py resume
python ~/ecc/skills/goal-loop/scripts/goal_loop.py tick  # iteration 2
python ~/ecc/skills/goal-loop/scripts/goal_loop.py tick  # iteration 3 (should hit max_iterations)
python ~/ecc/skills/goal-loop/scripts/goal_loop.py status  # should show completed
```

### 6.3 Validation Tests

```bash
# Test 2: Invalid stop condition
python scripts/validate.py --stop-condition "score_gte: 150"  # should fail (max 100)

# Test 3: Corrupt STATE.md
echo "invalid yaml" > /tmp/corrupt-STATE.md
python scripts/validate.py --state /tmp/corrupt-STATE.md  # should fail
```

---

## 7. Safety and Security

### 7.1 Filesystem Safety

Inspired by SkillLoop's `fs_safety.py`:

- All paths resolved with `Path.resolve()`
- `state_manager.py` validates that `STATE.md` path is under `project_root`
- Reject paths with `..` segments
- Reject absolute paths outside project root
- Atomic writes: temp file + rename

### 7.2 No Global State Mutation

- `goal-loop` only writes to `STATE.md` in the project root
- Never writes to `~/.claude/`, `~/.hermes/`, or global config
- No environment variable mutation

### 7.3 Input Validation

- All CLI arguments validated before any state mutation
- Stop condition values validated: `score_gte` 0-100, `max_iterations` >= 1
- Tags validated as non-empty strings

### 7.4 Secret Handling

- STATE.md may contain sensitive content (goal descriptions, action summaries)
- Document that users should not commit STATE.md to public repos
- Add `.gitignore` recommendation to SKILL.md

---

## 8. v1 Scope Boundary (Non-Negotiable)

**In scope:**
- Single-threaded loop
- One worker + one checker per loop
- STATE.md in project root only
- Manual resume (no auto-recovery)
- No nested loops
- Python 3.10+ only
- YAML-based stop-condition DSL

**Out of scope (v2):**
- Parallel worker pools
- Nested sub-loops
- Automatic crash recovery with journal
- Distributed STATE.md (git-synced)
- Webhook triggers
- Database backend for state

---

## 9. Dependencies

**Runtime dependencies:**
- Python 3.10+
- PyYAML (for STATE.md parsing)
- No other external packages

**Development dependencies:**
- pytest
- black (formatting)
- ruff (linting)

**ECC integration:**
- Reuses `skills/agent-self-evaluation/scripts/evaluate.py` if available (PR #2220)
- No hard dependencies on other ECC skills

---

## 10. Reference Material

### 10.1 SkillLoop Origins

| SkillLoop File | ECC Contribution |
|---|---|
| `skillloop/controller.py` — `ControllerRunReport`, `controller_tick()` | `scripts/goal_loop.py` orchestrator pattern |
| `skillloop/policy.py` — `EvaluationPolicy`, `LoopCondition` | `scripts/stop_condition.py` DSL design |
| `skillloop/fs_safety.py` — `resolve_under_root()`, `ensure_not_symlink_escape()` | Filesystem safety in `state_manager.py` |
| `skillloop/conditions.py` — `LoopCondition` | Stop-condition evaluation logic |
| `goal-loop/SKILL.md` (reference skill) | Behavioral spec for SKILL.md |

### 10.2 ECC Reference Skills

| ECC Skill | What to Learn From It |
|---|---|
| `skills/agent-self-evaluation/` | How to structure a skill with `scripts/`, how the evaluator works |
| `skills/skill-comply/` | How to structure a complex skill with tests |
| `skills/continuous-learning-v2/` | How to integrate hooks and shell scripts |

### 10.3 Clean Code Checklist

- [ ] Functions are short (< 20 lines)
- [ ] Functions do one thing
- [ ] Clear, descriptive names (no abbreviations)
- [ ] No duplication (DRY)
- [ ] Minimal arguments per function (ideally 0-2)
- [ ] No side effects in query functions
- [ ] Error handling is separate from happy path
- [ ] Unit tests for every module
- [ ] Comments explain WHY, not WHAT
- [ ] No magic numbers (use named constants)

---

## 11. Risk Mitigation

| Risk | Mitigation |
|---|---|
| ECC rejects Python scripts in skills | Point to `skill-comply`, `agent-self-evaluation` as precedents |
| PR #2220 evaluator API changes | `checker.py` has fallback rubric; doesn't hard-depend on evaluate.py |
| STATE.md schema needs changes in v2 | Version field in schema; `state_manager.py` validates version |
| Path traversal vulnerability | `fs_safety.py` patterns; resolve + validate under root |
| STATE.md corruption mid-write | Atomic writes (temp file + rename) |
| User commits STATE.md with secrets | Document `.gitignore` recommendation; don't store credentials |

---

## 12. Success Criteria

The contribution is complete when:

1. `skills/goal-loop/SKILL.md` exists and passes `validate-skills.js`
2. `skills/goal-loop/scripts/` contains working Python modules
3. All unit tests pass (`pytest tests/`)
4. All integration tests pass (full command flow)
5. All validation gates pass (see Section 5)
6. PR is opened with clear description and test evidence
7. Clean Code principles verified (function length, naming, duplication)

---

## 13. Quick Reference for Sub-Agents

When spawning sub-agents to build this, provide each agent with:

1. **This plan document** (or relevant section)
2. **The specific module they're building** (e.g., "Implement `state_manager.py`")
3. **Interface contract** (dataclass signatures, method names, return types)
4. **Test file they must produce** (filename and at least 3 test cases)
5. **Clean Code constraints** (function length, naming rules)
6. **Filesystem safety rules** (resolve paths, validate under root, atomic writes)
7. **Example usage** (how the module will be called by `goal_loop.py`)

---

## 14. Pre-Filled Sub-Agent Prompts (Copy-Paste Ready)

These prompts are ready to hand to sub-agents. Do not modify the spec inside them.

### Agent A: state_manager.py + tests

```
You are building the state_manager.py module for the ECC goal-loop skill.

REPO CONTEXT:
- ECC is at ~/ecc (cloned from https://github.com/affaan-m/ECC)
- Your working directory: ~/ecc/skills/goal-loop/
- This skill manages loop state in a project-local STATE.md file

FILE TO CREATE:
- scripts/state_manager.py
- tests/test_state_manager.py

INTERFACE CONTRACT (implement exactly these classes and methods):

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

STATE_VERSION = "1.0"
STATE_FILENAME = "STATE.md"

@dataclass
class IterationRecord:
    id: int
    started_at: str
    finished_at: str
    worker_actions: list[str]
    checker_score: int
    checker_tags: list[str]
    state: str  # "passed", "failed", "pending"

@dataclass
class StopCondition:
    score_gte: Optional[int] = None
    required_tags: list[str] = None
    forbidden_tags: list[str] = None
    max_iterations: int = 20

@dataclass
class GoalLoopState:
    version: str
    goal: str
    started_at: str
    checker_persona: str
    stop_condition: StopCondition
    iterations: list[IterationRecord]
    current_iteration: int
    status: str  # "running", "paused", "completed", "aborted"
    conclusion: Optional[dict[str, Any]] = None

class StateManager:
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root).resolve()
        self.state_path = self.project_root / STATE_FILENAME

    def exists(self) -> bool: ...
    def load(self) -> GoalLoopState: ...
    def save(self, state: GoalLoopState) -> None: ...
    def create_initial(self, goal: str, checker_persona: str, stop_condition: StopCondition) -> GoalLoopState: ...
    def append_iteration(self, record: IterationRecord) -> GoalLoopState: ...
    def set_status(self, status: str) -> GoalLoopState: ...
    def set_conclusion(self, reason: str, final_score: Optional[int] = None) -> GoalLoopState: ...

REQUIREMENTS:
1. load() must parse STATE.md YAML frontmatter (between --- markers) + markdown body
2. save() must write YAML frontmatter + markdown body, atomically (temp file + rename)
3. All paths resolved under project_root; raise ValueError if path escapes project_root
4. Schema version "1.0" only; raise ValueError on unknown version
5. create_initial() sets started_at to ISO8601 UTC, status to "running", current_iteration to 0
6. append_iteration() increments current_iteration, appends to iterations list, saves
7. set_status() updates status and saves
8. set_conclusion() writes conclusion dict, sets status to "completed" or "aborted", saves

CLEAN CODE (mandatory):
- Every function <= 20 lines
- No abbreviations (checker_score not cs, current_iteration not cur_iter)
- Single responsibility per function
- No magic numbers (use named constants)
- Fail fast: validate inputs at function entry

TESTS (tests/test_state_manager.py):
Use pytest. Use tmp_path fixture for isolation. Minimum 5 tests:
1. test_create_initial_creates_valid_state
2. test_save_and_load_roundtrip
3. test_append_iteration_increments_counter
4. test_load_rejects_unknown_version
5. test_path_traversal_rejected
6. test_atomic_write_no_partial_state

DELIVERABLE:
- scripts/state_manager.py
- tests/test_state_manager.py
- Run: cd ~/ecc/skills/goal-loop && python -m pytest tests/test_state_manager.py -v
- Report: pass/fail for each test
```

### Agent B: stop_condition.py + tests

```
You are building the stop_condition.py module for the ECC goal-loop skill.

REPO CONTEXT:
- ECC is at ~/ecc (cloned from https://github.com/affaan-m/ECC)
- Your working directory: ~/ecc/skills/goal-loop/
- This module parses and evaluates the stop-condition DSL

FILE TO CREATE:
- scripts/stop_condition.py
- tests/test_stop_condition.py

INTERFACE CONTRACT:

from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class StopCondition:
    score_gte: Optional[int] = None
    required_tags: list[str] = None
    forbidden_tags: list[str] = None
    max_iterations: int = 20

    @classmethod
    def from_dict(cls, data: dict) -> "StopCondition": ...
    @classmethod
    def from_yaml_string(cls, yaml_str: str) -> "StopCondition": ...
    def evaluate(self, iteration_score: int, iteration_tags: list[str], current_iteration: int) -> "StopResult": ...

@dataclass(frozen=True)
class StopResult:
    should_stop: bool
    reason: Optional[str] = None

REQUIREMENTS:
1. from_dict() validates: score_gte must be 0-100 or None, max_iterations must be >= 1, tags must be list of strings
2. from_yaml_string() parses YAML and delegates to from_dict()
3. evaluate() returns StopResult with should_stop and reason
4. Evaluation order (exact):
   a. If current_iteration >= max_iterations → should_stop=True, reason="max_iterations_reached"
   b. If any forbidden_tag in iteration_tags → should_stop=True, reason="forbidden_tag_hit"
   c. If score_gte is set AND iteration_score >= score_gte AND all required_tags in iteration_tags → should_stop=True, reason="condition_met"
   d. Otherwise → should_stop=False, reason=None
5. If score_gte is None, skip score check in step c
6. If required_tags is empty, skip tag check in step c

CLEAN CODE (mandatory):
- Every function <= 20 lines
- No abbreviations
- Single responsibility per function
- No magic numbers
- Fail fast: validate inputs at function entry

TESTS (tests/test_stop_condition.py):
Use pytest. Minimum 6 tests:
1. test_max_iterations_triggers_stop
2. test_forbidden_tag_triggers_stop
3. test_score_and_tags_met_triggers_stop
4. test_score_below_threshold_continues
5. test_missing_required_tag_continues
6. test_from_dict_rejects_invalid_score
7. test_from_dict_rejects_negative_max_iterations

DELIVERABLE:
- scripts/stop_condition.py
- tests/test_stop_condition.py
- Run: cd ~/ecc/skills/goal-loop && python -m pytest tests/test_stop_condition.py -v
- Report: pass/fail for each test
```

### Agent C: checker.py + validate.py + tests

```
You are building the checker.py and validate.py modules for the ECC goal-loop skill.

REPO CONTEXT:
- ECC is at ~/ecc (cloned from https://github.com/affaan-m/ECC)
- Your working directory: ~/ecc/skills/goal-loop/
- checker.py invokes a checker persona to evaluate each iteration
- validate.py is a standalone CLI for validating STATE.md and stop conditions
- The skill reuses agent-self-evaluation from PR #2220 if available

FILES TO CREATE:
- scripts/checker.py
- scripts/validate.py
- tests/test_checker.py

INTERFACE CONTRACT for checker.py:

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass(frozen=True)
class CheckerResult:
    score: int  # 0-100
    tags: list[str]
    rationale: str

class Checker:
    def __init__(self, persona: str, project_root: Path):
        self.persona = persona
        self.project_root = Path(project_root).resolve()

    def evaluate(self, worker_actions: list[str], context_files: Optional[list[Path]] = None) -> CheckerResult: ...
    def _invoke_agent_evaluator(self, worker_actions: list[str]) -> Optional[CheckerResult]: ...
    def _fallback_rubric(self, worker_actions: list[str]) -> CheckerResult: ...

REQUIREMENTS for checker.py:
1. evaluate() first tries _invoke_agent_evaluator(), then falls back to _fallback_rubric()
2. _invoke_agent_evaluator() looks for ~/ecc/skills/agent-self-evaluation/scripts/evaluate.py
   - If found, invoke it as a subprocess with worker_actions as JSON stdin
   - Parse its JSON stdout into CheckerResult
   - If subprocess fails or returns invalid JSON, return None (triggers fallback)
3. _fallback_rubric() is a lightweight regex-based rubric (no external dependencies):
   - Score starts at 70
   - +10 if any action contains "test" or "verify"
   - +10 if any action contains "validate" or "check"
   - -20 if any action contains "rm -rf" or "eval("
   - -20 if any action contains password, secret, token, api_key (case insensitive)
   - Tags: add "verified" if score >= 80, add "security_risk" if any negative match
   - Rationale: brief text explaining score
4. Never modifies filesystem; read-only evaluation
5. Returns CheckerResult regardless of which path was taken

INTERFACE CONTRACT for validate.py:

import argparse
import sys
from pathlib import Path

def validate_state_file(path: Path) -> bool: ...
def validate_stop_condition(yaml_str: str) -> bool: ...
def main(): ...

REQUIREMENTS for validate.py:
1. CLI: python validate.py --state <path> OR python validate.py --stop-condition "yaml string"
2. validate_state_file() loads STATE.md via state_manager.py, returns True if valid
3. validate_stop_condition() parses YAML via stop_condition.py, returns True if valid
4. Exit code 0 if valid, 1 if invalid
5. Print specific error messages to stderr

CLEAN CODE (mandatory):
- Every function <= 20 lines
- No abbreviations
- Single responsibility per function
- No magic numbers
- Fail fast

TESTS (tests/test_checker.py):
Use pytest. Use monkeypatch for subprocess mocking. Minimum 4 tests:
1. test_fallback_rubric_scores_correctly
2. test_fallback_rubric_detects_security_risk
3. test_fallback_rubric_rewards_verification
4. test_evaluate_uses_fallback_when_evaluator_missing

DELIVERABLE:
- scripts/checker.py
- scripts/validate.py
- tests/test_checker.py
- Run: cd ~/ecc/skills/goal-loop && python -m pytest tests/test_checker.py -v
- Also run: python scripts/validate.py --stop-condition "score_gte: 80\nmax_iterations: 5"
- Report: pass/fail for each test and validation
```

### Agent D: goal_loop.py + integration tests (Phase 3)

```
You are building the goal_loop.py orchestrator for the ECC goal-loop skill.

REPO CONTEXT:
- ECC is at ~/ecc (cloned from https://github.com/affaan-m/ECC)
- Your working directory: ~/ecc/skills/goal-loop/
- This is the CLI entry point that orchestrates the entire loop
- state_manager.py, stop_condition.py, and checker.py are already implemented

FILE TO CREATE:
- scripts/goal_loop.py
- tests/test_goal_loop.py

INTERFACE CONTRACT:

import argparse
import sys
from pathlib import Path

def cmd_start(args): ...
def cmd_tick(args): ...
def cmd_status(args): ...
def cmd_pause(args): ...
def cmd_resume(args): ...
def cmd_stop(args): ...
def main(): ...

REQUIREMENTS:
1. CLI commands:
   - start --goal <str> --checker <str> --max-iterations <int> --score-gte <int> --required-tags [list] --forbidden-tags [list] --project-root <path>
   - tick --project-root <path>
   - status --project-root <path>
   - pause --project-root <path>
   - resume --project-root <path>
   - stop --reason <str> --project-root <path>
2. cmd_start(): Call StateManager.create_initial(), save STATE.md, print confirmation
3. cmd_tick(): Load state, verify status is "running", collect worker actions (simulate or read from args), invoke Checker.evaluate(), append iteration via StateManager, evaluate stop condition, if stopped call set_conclusion()
4. cmd_status(): Load state, print human-readable summary (goal, status, current iteration, last score)
5. cmd_pause(): set_status("paused")
6. cmd_resume(): set_status("running")
7. cmd_stop(): set_conclusion(reason=args.reason)
8. All commands validate that STATE.md exists (except start)
9. All commands catch exceptions and print clean error messages to stderr

CLEAN CODE (mandatory):
- Every function <= 20 lines
- No abbreviations
- Single responsibility per function
- No duplication (reuse StateManager, StopCondition, Checker)
- No global state

TESTS (tests/test_goal_loop.py):
Use pytest. Use tmp_path and subprocess.run. Minimum 5 tests:
1. test_start_creates_state_file
2. test_tick_appends_iteration
3. test_pause_and_resume_toggle_status
4. test_stop_writes_conclusion
5. test_resume_continues_from_saved_state
6. test_status_shows_current_progress

DELIVERABLE:
- scripts/goal_loop.py
- tests/test_goal_loop.py
- Run: cd ~/ecc/skills/goal-loop && python -m pytest tests/test_goal_loop.py -v
- Also run full integration: start -> tick -> status -> pause -> resume -> tick -> stop
- Report: pass/fail for each test
```

### Agent E: templates/STATE.md + hooks/goal-loop.json (Phase 3)

```
You are building the template and hook files for the ECC goal-loop skill.

REPO CONTEXT:
- ECC is at ~/ecc (cloned from https://github.com/affaan-m/ECC)
- Your working directory: ~/ecc/skills/goal-loop/

FILES TO CREATE:
- templates/STATE.md
- hooks/goal-loop.json

REQUIREMENTS for templates/STATE.md:
1. Jinja2-style placeholders: {{ goal }}, {{ started_at }}, {{ checker_persona }}, {{ score_gte }}, {{ required_tags }}, {{ forbidden_tags }}, {{ max_iterations }}
2. YAML frontmatter between --- markers
3. Markdown body for human readability
4. Include: goal, started time, status, checker, stop condition summary, empty iterations section
5. Schema must match state_manager.py's GoalLoopState exactly

REQUIREMENTS for hooks/goal-loop.json:
1. Valid JSON following ECC hook schema
2. event: "PostToolUse"
3. match on tool: "Bash" with command containing "goal-loop"
4. action: notify user to check status
5. This is optional for v1; primary interface is slash commands

DELIVERABLE:
- templates/STATE.md
- hooks/goal-loop.json
- Verify: python -c "import yaml; yaml.safe_load(open('templates/STATE.md').read().split('---')[1])" succeeds
- Report: success/failure
```

### Agent F: SKILL.md final documentation (Phase 4)

```
You are writing the SKILL.md documentation for the ECC goal-loop skill.

REPO CONTEXT:
- ECC is at ~/ecc (cloned from https://github.com/affaan-m/ECC)
- Your working directory: ~/ecc/skills/goal-loop/
- All scripts, templates, and tests are already implemented

FILE TO CREATE:
- SKILL.md

REQUIREMENTS:
1. YAML frontmatter with: name, version, description, author, tags, commands (list with name, description, usage)
2. Overview section explaining what goal-loop does
3. Architecture section describing maker-checker flow
4. Detailed command documentation for all 6 commands
5. Stop-Condition DSL syntax and semantics
6. STATE.md schema documentation
7. Two concrete examples: bug-fix loop and documentation update loop
8. Integration with agent-self-evaluation (PR #2220) section
9. Safety section: path traversal prevention, no global state, .gitignore recommendation
10. Clean, professional tone matching existing ECC skills

VALIDATION:
- Run: cd ~/ecc && node scripts/ci/validate-skills.js
- Must pass without errors for skills/goal-loop/

DELIVERABLE:
- SKILL.md
- Validation output (pass/fail)
```

---

End of plan.
