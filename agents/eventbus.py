"""Event bus: typed publish/subscribe used by the orchestrator and viewers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class EventType(str, Enum):
    TASK_ASSIGNED = "task.assigned"
    TASK_STARTED = "task.started"
    ARTIFACT_COMMITTED = "artifact.committed"
    TESTS_PASSED = "tests.passed"
    VIEWER_APPROVED = "viewer.approved"
    VIEWER_REJECTED = "viewer.rejected"
    BLOCKER_RAISED = "blocker.raised"
    PHASE_GATED = "phase.gated"


@dataclass
class Event:
    type: EventType
    source: str
    payload: dict = field(default_factory=dict)

    def __str__(self) -> str:
        return f"<{self.type.value} from={self.source}>"


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[EventType, list[Callable[[Event], None]]] = {}

    def subscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        self._subscribers.setdefault(event_type, []).append(handler)

    def publish(self, event: Event) -> None:
        for handler in self._subscribers.get(event.type, []):
            handler(event)
