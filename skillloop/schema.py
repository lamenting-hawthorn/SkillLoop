from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    result: str | None = None
    success: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "arguments": self.arguments,
            "result": self.result,
            "success": self.success,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolCall":
        return cls(
            name=str(data.get("name", "")),
            arguments=dict(data.get("arguments") or {}),
            result=data.get("result"),
            success=data.get("success"),
        )


@dataclass
class AgentMessage:
    role: str
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.role not in {"system", "user", "assistant", "tool"}:
            raise ValueError(f"invalid message role: {self.role}")
        if self.content is None:
            self.content = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "tool_calls": [call.to_dict() for call in self.tool_calls],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentMessage":
        return cls(
            role=str(data.get("role", "user")),
            content=str(data.get("content") or ""),
            tool_calls=[ToolCall.from_dict(item) for item in data.get("tool_calls", [])],
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class AgentTrace:
    source: str
    messages: list[AgentMessage]
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = field(default_factory=now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.messages:
            raise ValueError("trace must contain at least one message")
        if not self.source:
            raise ValueError("trace source is required")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "created_at": self.created_at,
            "metadata": self.metadata,
            "messages": [message.to_dict() for message in self.messages],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentTrace":
        return cls(
            id=str(data.get("id") or uuid4().hex),
            source=str(data.get("source") or "unknown"),
            created_at=str(data.get("created_at") or now_iso()),
            metadata=dict(data.get("metadata") or {}),
            messages=[AgentMessage.from_dict(item) for item in data.get("messages", [])],
        )


@dataclass
class Evaluation:
    trace_id: str
    score: int
    tags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "trace_id": self.trace_id,
            "score": self.score,
            "tags": self.tags,
            "notes": self.notes,
            "created_at": self.created_at,
        }


@dataclass
class Proposal:
    trace_id: str
    kind: str
    title: str
    content: str
    reason: str
    id: str = field(default_factory=lambda: uuid4().hex)
    status: str = "pending"
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "trace_id": self.trace_id,
            "kind": self.kind,
            "title": self.title,
            "content": self.content,
            "reason": self.reason,
            "status": self.status,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Proposal":
        return cls(
            id=str(data.get("id") or uuid4().hex),
            trace_id=str(data.get("trace_id") or ""),
            kind=str(data.get("kind") or "memory"),
            title=str(data.get("title") or "Untitled"),
            content=str(data.get("content") or ""),
            reason=str(data.get("reason") or ""),
            status=str(data.get("status") or "pending"),
            created_at=str(data.get("created_at") or now_iso()),
        )
