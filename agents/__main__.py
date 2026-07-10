"""CLI to inspect and simulate the agent orchestration topology."""

from __future__ import annotations

import sys

from .orchestrator import Orchestrator
from .topology import (
    IMPLEMENTATION_AGENTS,
    ORCHESTRATOR,
    VIEWER_AGENTS,
)


def _print_topology() -> None:
    print("Agent topology\n" + "=" * 40)
    for a in IMPLEMENTATION_AGENTS:
        print(f"\n[{a.role.value}] {a.id}")
        print(f"  task : {a.task}")
        print(f"  scope: {a.scope}")
        print(f"  deps : {a.depends_on or 'none'}")
        print(f"  wt   : {a.worktree}")
    for v in VIEWER_AGENTS:
        print(f"\n[{v.role.value}] {v.id}")
        print(f"  task : {v.task}")
        print(f"  watch: {v.subscribes}")
    print(f"\n[{ORCHESTRATOR.role.value}] {ORCHESTRATOR.id}")
    print(f"  task : {ORCHESTRATOR.task}")


def _simulate() -> None:
    orch = Orchestrator()
    errors = orch.validate_topology()
    if errors:
        print("TOPOLOGY ERRORS:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("Topology valid: no scope overlap, dependencies resolve.\n")
    print("Assignable now:", [a.id for a in orch.assignable()])
    orch.complete("impl.phase0")
    print("After impl.phase0 completes, assignable:", [a.id for a in orch.assignable()])
    orch.complete("impl.cli")
    orch.complete("impl.persistence")
    print("After cli+persistence, assignable:", [a.id for a in orch.assignable()])
    print()
    print(orch.report())


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "topology"
    if cmd == "topology":
        _print_topology()
    elif cmd == "simulate":
        _simulate()
    else:
        print(f"unknown command: {cmd} (use 'topology' or 'simulate')")
        sys.exit(2)


if __name__ == "__main__":
    main()
