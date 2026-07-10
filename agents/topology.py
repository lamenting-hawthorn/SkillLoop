"""Agent topology for the SkillLoop transformation.

Each implementation agent owns a disjoint file scope (isolated in its own git
worktree) so concurrent work cannot collide. Viewers are read-only observers
subscribed to bus events. Constraints are enforced by the orchestrator before
assignment and before merge.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum


class Role(StrEnum):
    IMPLEMENTATION = "implementation"
    VIEWER = "viewer"
    ORCHESTRATOR = "orchestrator"


@dataclass
class Constraint:
    id: str
    description: str
    check: Callable[[dict], bool] | None = None


@dataclass
class Agent:
    id: str
    role: Role
    task: str
    scope: list[str]
    depends_on: list[str] = field(default_factory=list)
    constraints: list[Constraint] = field(default_factory=list)
    subscribes: list[str] = field(default_factory=list)
    worktree: str | None = None


_IMPL_CONSTRAINTS = [
    Constraint("no_scope_overlap", "File scope must not intersect any other implementation agent."),
    Constraint(
        "backward_compat_cli", "Public CLI syntax and persisted schema must stay compatible."
    ),
    Constraint("review_gated_writes", "Side effects remain review-gated and project-local."),
    Constraint("atomic_migrations", "Persistence migrations must be explicit and atomic."),
]

PHASE0 = Agent(
    id="impl.phase0",
    role=Role.IMPLEMENTATION,
    task="Stabilize current work: split packaging vs user-work commits, fix whitespace in review/queue.py, run wheel + isolated install smoke test, verify v1->v2 SQLite upgrade with no data loss.",
    scope=["pyproject.toml", "CHANGELOG.md", "skillloop/review/queue.py"],
    depends_on=[],
    constraints=_IMPL_CONSTRAINTS,
    worktree=".worktrees/phase0",
)

CLI = Agent(
    id="impl.cli",
    role=Role.IMPLEMENTATION,
    task="Phase 2: split cli.py (749 lines) into interfaces/cli/* modules; introduce typed request objects for setup/ingest/export/training; move orchestration into application services; standardize errors/exit codes. Keep CLI syntax backward-compatible.",
    scope=["skillloop/cli.py", "skillloop/interfaces/**", "skillloop/application/**"],
    depends_on=["impl.phase0"],
    constraints=_IMPL_CONSTRAINTS,
    worktree=".worktrees/cli",
)

PERSISTENCE = Agent(
    id="impl.persistence",
    role=Role.IMPLEMENTATION,
    task="Phase 3: extract migrations into a registry; atomic transactions; pagination/limits on list APIs; batch trace/eval/proposal ops; stream large JSONL; explicit controller-tick boundaries; evaluate WAL after concurrency tests.",
    scope=["skillloop/store.py", "skillloop/infrastructure/sqlite/**", "skillloop/schema.py"],
    depends_on=["impl.phase0"],
    constraints=_IMPL_CONSTRAINTS,
    worktree=".worktrees/persistence",
)

SECURITY = Agent(
    id="impl.security",
    role=Role.IMPLEMENTATION,
    task="Phase 4: replace non-atomic JSON/config writes with temp-file + atomic rename; error taxonomy (config/input/persistence/connector/policy); validate policy fields + adapter names; trace/message size limits; PII redaction; sanitized controller error reports; conservative file perms.",
    scope=["skillloop/fs_safety.py", "skillloop/sanitize.py", "skillloop/policy.py"],
    depends_on=["impl.phase0"],
    constraints=_IMPL_CONSTRAINTS,
    worktree=".worktrees/security",
)

SERVICES = Agent(
    id="impl.services",
    role=Role.IMPLEMENTATION,
    task="Phase 5: define ServiceManager port; keep launchd as one impl; add systemd user-service for Linux; install/status/uninstall parity; explicit activation only. No OS-specific code in application logic.",
    scope=[
        "skillloop/service.py",
        "skillloop/ports/service_manager.py",
        "skillloop/infrastructure/services/**",
    ],
    depends_on=["impl.phase0"],
    constraints=_IMPL_CONSTRAINTS,
    worktree=".worktrees/services",
)

QUALITY = Agent(
    id="impl.quality",
    role=Role.IMPLEMENTATION,
    task="Phase 6: add Ruff lint/format; incremental typing on domain+application; coverage reporting; 3.11-3.13; wheel+sdist tests; clean-env E2E (install/init/ingest/eval/distill/review/apply/export/upgrade); backward-compat tests.",
    scope=["ruff.toml", "tests/**", ".github/workflows/ci.yml"],
    depends_on=["impl.cli", "impl.persistence"],
    constraints=_IMPL_CONSTRAINTS,
    worktree=".worktrees/quality",
)

VIEW_ARCH = Agent(
    id="view.arch",
    role=Role.VIEWER,
    task="Verify layering: domain code never imports sqlite/argparse/launchd/hermes; CLI modules contain parsing/presentation only; application services own no infra details.",
    scope=["skillloop/domain/**", "skillloop/interfaces/**", "skillloop/application/**"],
    depends_on=[],
    constraints=[],
    subscribes=["artifact.committed"],
)

VIEW_CI = Agent(
    id="view.ci",
    role=Role.VIEWER,
    task="Verify tests pass, compile check passes, git diff --check clean, and wheel builds for every committed artifact.",
    scope=["tests/**", "skillloop/**"],
    depends_on=[],
    constraints=[],
    subscribes=["artifact.committed", "tests.passed"],
)

VIEW_SEC = Agent(
    id="view.sec",
    role=Role.VIEWER,
    task="Verify no secret/trace leakage in diagnostics or controller reports; generated state uses conservative permissions; redaction covers new PII policies.",
    scope=["skillloop/sanitize.py", "skillloop/diagnostics.py", "skillloop/controller.py"],
    depends_on=[],
    constraints=[],
    subscribes=["artifact.committed"],
)

ORCHESTRATOR = Agent(
    id="orchestrator",
    role=Role.ORCHESTRATOR,
    task="Assign tasks after dependency gating; dispatch viewers on commit events; require viewer approval before merge; sequence phases.",
    scope=[],
    depends_on=[],
    constraints=[],
)

IMPLEMENTATION_AGENTS = [PHASE0, CLI, PERSISTENCE, SECURITY, SERVICES, QUALITY]
VIEWER_AGENTS = [VIEW_ARCH, VIEW_CI, VIEW_SEC]
ALL_AGENTS = IMPLEMENTATION_AGENTS + VIEWER_AGENTS + [ORCHESTRATOR]
