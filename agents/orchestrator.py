"""Orchestrator: assigns tasks with dependency gating, detects scope overlap,
dispatches viewers on events, and requires viewer approval before merge."""

from __future__ import annotations

from dataclasses import dataclass, field

from .eventbus import Event, EventBus, EventType
from .topology import (
    ALL_AGENTS,
    IMPLEMENTATION_AGENTS,
    VIEWER_AGENTS,
    Agent,
)


@dataclass
class Orchestrator:
    bus: EventBus = field(default_factory=EventBus)
    _done: set[str] = field(default_factory=set)
    _approved: set[str] = field(default_factory=set)
    _blockers: list[Event] = field(default_factory=list)

    def __post_init__(self) -> None:
        for viewer in VIEWER_AGENTS:
            for evt in viewer.subscribes:
                self.bus.subscribe(EventType(evt), self._on_viewer_event)

    def validate_topology(self) -> list[str]:
        errors: list[str] = []
        impl = IMPLEMENTATION_AGENTS
        for i in range(len(impl)):
            for j in range(i + 1, len(impl)):
                overlap = self._scope_overlap(impl[i], impl[j])
                if overlap:
                    errors.append(
                        f"scope overlap between {impl[i].id} and {impl[j].id}: {sorted(overlap)}"
                    )
        ids = [a.id for a in ALL_AGENTS]
        if len(ids) != len(set(ids)):
            errors.append("duplicate agent ids")
        for a in ALL_AGENTS:
            for dep in a.depends_on:
                if dep not in ids:
                    errors.append(f"{a.id} depends on unknown agent {dep}")
        return errors

    def _scope_overlap(self, a: Agent, b: Agent) -> set[str]:
        files_a = {p for p in a.scope if "**" not in p}
        files_b = {p for p in b.scope if "**" not in p}
        exact = set(files_a) & set(files_b)
        wildcard = set()
        for pat in a.scope + b.scope:
            if "**" in pat:
                prefix = pat.split("**")[0]
                for other in list(files_a) + list(files_b):
                    if other.startswith(prefix):
                        wildcard.add(other)
        return exact | wildcard

    def ready(self, agent: Agent) -> bool:
        return all(d in self._done for d in agent.depends_on)

    def assignable(self) -> list[Agent]:
        return [a for a in IMPLEMENTATION_AGENTS if a.id not in self._done and self.ready(a)]

    def complete(self, agent_id: str) -> None:
        self._done.add(agent_id)
        self.bus.publish(Event(EventType.TASK_ASSIGNED, agent_id, {"completed": True}))

    def submit_artifact(self, agent_id: str) -> None:
        self.bus.publish(Event(EventType.ARTIFACT_COMMITTED, agent_id))

    def _on_viewer_event(self, event: Event) -> None:
        if event.type == EventType.VIEWER_APPROVED:
            self._approved.add(event.payload.get("agent", event.source))
        elif event.type == EventType.VIEWER_REJECTED:
            self._blockers.append(event)
        elif event.type == EventType.ARTIFACT_COMMITTED:
            for viewer in VIEWER_AGENTS:
                self.bus.publish(Event(EventType.TASK_STARTED, viewer.id, {"target": event.source}))

    def can_merge(self, agent_id: str) -> bool:
        needed = {v.id for v in VIEWER_AGENTS}
        ok = needed.issubset(self._approved) and not self._blockers
        if ok:
            self._done.add(agent_id)
        return ok

    def report(self) -> str:
        lines = ["Orchestrator state", "=" * 40]
        for a in IMPLEMENTATION_AGENTS:
            state = "done" if a.id in self._done else ("ready" if self.ready(a) else "blocked")
            lines.append(f"  {a.id:<16} [{state}] deps={a.depends_on}")
        lines.append("-" * 40)
        lines.append(f"  viewers approved: {sorted(self._approved)}")
        lines.append(f"  blockers: {len(self._blockers)}")
        return "\n".join(lines)
