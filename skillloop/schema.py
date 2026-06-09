from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from skillloop.sanitize import redact_data, redact_secrets

TRACE_SCHEMA_VERSION = "1.1"
TOOL_CALL_STATUSES = {"pending", "running", "success", "error", "cancelled", "unknown"}
PROPOSAL_STATUSES = {"pending", "approved", "applied", "rejected"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _coerce_artifact_refs(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def _status_from_success(success: bool | None) -> str:
    if success is True:
        return "success"
    if success is False:
        return "error"
    return "unknown"


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    result: str | None = None
    success: bool | None = None
    id: str = field(default_factory=lambda: uuid4().hex)
    started_at: str | None = None
    ended_at: str | None = None
    duration_ms: int | None = None
    exit_code: int | None = None
    status: str | None = None
    error_type: str | None = None
    artifact_refs: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.name = str(self.name or "")
        self.arguments = redact_data(dict(self.arguments or {}))
        if self.result is not None:
            self.result = str(redact_secrets(str(self.result)))
        self.id = str(self.id or uuid4().hex)
        self.started_at = str(self.started_at) if self.started_at is not None else None
        self.ended_at = str(self.ended_at) if self.ended_at is not None else None
        self.duration_ms = int(self.duration_ms) if self.duration_ms is not None else None
        self.exit_code = int(self.exit_code) if self.exit_code is not None else None
        self.error_type = str(self.error_type) if self.error_type is not None else None
        self.artifact_refs = _coerce_artifact_refs(self.artifact_refs)
        self.status = str(self.status or _status_from_success(self.success))
        if self.status not in TOOL_CALL_STATUSES:
            self.status = "unknown"
        if self.success is None and self.status in {"success", "error"}:
            self.success = self.status == "success"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "arguments": self.arguments,
            "result": self.result,
            "success": self.success,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_ms": self.duration_ms,
            "exit_code": self.exit_code,
            "status": self.status,
            "error_type": self.error_type,
            "artifact_refs": self.artifact_refs,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolCall":
        return cls(
            id=str(data.get("id") or uuid4().hex),
            name=str(data.get("name", "")),
            arguments=dict(data.get("arguments") or {}),
            result=data.get("result"),
            success=data.get("success"),
            started_at=data.get("started_at"),
            ended_at=data.get("ended_at"),
            duration_ms=data.get("duration_ms"),
            exit_code=data.get("exit_code"),
            status=data.get("status"),
            error_type=data.get("error_type"),
            artifact_refs=_coerce_artifact_refs(data.get("artifact_refs")),
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
        self.content = redact_secrets(str(self.content))
        self.metadata = redact_data(dict(self.metadata or {}))

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
    schema_version: str = TRACE_SCHEMA_VERSION
    runtime: dict[str, Any] = field(default_factory=dict)
    adapter: dict[str, Any] = field(default_factory=dict)
    raw_artifact_ref: str | None = None
    raw_trace_sha256: str | None = None
    normalized_trace_sha256: str | None = None

    def __post_init__(self) -> None:
        if not self.messages:
            raise ValueError("trace must contain at least one message")
        if not self.source:
            raise ValueError("trace source is required")
        self.id = str(self.id or uuid4().hex)
        self.created_at = str(self.created_at or now_iso())
        self.schema_version = str(self.schema_version or "1.0")
        self.metadata = redact_data(dict(self.metadata or {}))
        self.runtime = redact_data(dict(self.runtime or {}))
        self.adapter = redact_data(dict(self.adapter or {}))
        self.raw_artifact_ref = str(self.raw_artifact_ref) if self.raw_artifact_ref is not None else None
        self.raw_trace_sha256 = str(self.raw_trace_sha256) if self.raw_trace_sha256 is not None else None
        self.normalized_trace_sha256 = str(self.normalized_trace_sha256) if self.normalized_trace_sha256 is not None else None

    def _dict_for_hash(self) -> dict[str, Any]:
        data = self.to_dict(include_hashes=False)
        data.pop("raw_trace_sha256", None)
        data.pop("normalized_trace_sha256", None)
        return data

    def compute_normalized_sha256(self) -> str:
        return sha256_text(stable_json_dumps(self._dict_for_hash()))

    def to_dict(self, include_hashes: bool = True) -> dict[str, Any]:
        data = {
            "id": self.id,
            "schema_version": self.schema_version,
            "source": self.source,
            "created_at": self.created_at,
            "runtime": self.runtime,
            "adapter": self.adapter,
            "metadata": self.metadata,
            "raw_artifact_ref": self.raw_artifact_ref,
            "messages": [message.to_dict() for message in self.messages],
        }
        if include_hashes:
            data["raw_trace_sha256"] = self.raw_trace_sha256
            data["normalized_trace_sha256"] = self.normalized_trace_sha256 or self.compute_normalized_sha256()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentTrace":
        return cls(
            id=str(data.get("id") or uuid4().hex),
            schema_version=str(data.get("schema_version") or "1.0"),
            source=str(data.get("source") or "unknown"),
            created_at=str(data.get("created_at") or now_iso()),
            runtime=dict(data.get("runtime") or {}),
            adapter=dict(data.get("adapter") or {}),
            metadata=dict(data.get("metadata") or {}),
            raw_artifact_ref=data.get("raw_artifact_ref"),
            raw_trace_sha256=data.get("raw_trace_sha256"),
            normalized_trace_sha256=data.get("normalized_trace_sha256"),
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
    evaluator_name: str = "rubric"
    evaluator_version: str = "1.0"
    evidence: list[dict[str, Any]] = field(default_factory=list)
    created_from_trace_schema_version: str = "1.0"

    def __post_init__(self) -> None:
        self.trace_id = str(self.trace_id)
        self.score = int(self.score)
        self.tags = [str(tag) for tag in self.tags]
        self.notes = [str(note) for note in self.notes]
        self.evaluator_name = str(self.evaluator_name or "unknown")
        self.evaluator_version = str(self.evaluator_version or "0")
        self.evidence = [redact_data(dict(item or {})) for item in self.evidence]
        self.created_from_trace_schema_version = str(self.created_from_trace_schema_version or "1.0")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "trace_id": self.trace_id,
            "score": self.score,
            "tags": self.tags,
            "notes": self.notes,
            "created_at": self.created_at,
            "evaluator_name": self.evaluator_name,
            "evaluator_version": self.evaluator_version,
            "evidence": self.evidence,
            "created_from_trace_schema_version": self.created_from_trace_schema_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Evaluation":
        return cls(
            id=str(data.get("id") or uuid4().hex),
            trace_id=str(data.get("trace_id") or ""),
            score=int(data.get("score") or 0),
            tags=[str(tag) for tag in data.get("tags", [])],
            notes=[str(note) for note in data.get("notes", [])],
            created_at=str(data.get("created_at") or now_iso()),
            evaluator_name=str(data.get("evaluator_name") or "rubric"),
            evaluator_version=str(data.get("evaluator_version") or "1.0"),
            evidence=[dict(item or {}) for item in data.get("evidence", [])],
            created_from_trace_schema_version=str(data.get("created_from_trace_schema_version") or "1.0"),
        )


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
    content_hash: str | None = None
    applied_at: str | None = None
    source_trace_schema_version: str = "1.0"
    source_evaluation_id: str | None = None

    def __post_init__(self) -> None:
        self.content = str(self.content or "")
        self.content_hash = str(self.content_hash or sha256_text(stable_json_dumps({"kind": self.kind, "content": self.content})))
        self.status = str(self.status or "pending")
        if self.status not in PROPOSAL_STATUSES:
            self.status = "pending"
        self.applied_at = str(self.applied_at) if self.applied_at is not None else None
        self.source_trace_schema_version = str(self.source_trace_schema_version or "1.0")
        self.source_evaluation_id = str(self.source_evaluation_id) if self.source_evaluation_id is not None else None

    def mark_applied(self) -> None:
        self.status = "applied"
        self.applied_at = now_iso()

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
            "content_hash": self.content_hash,
            "applied_at": self.applied_at,
            "source_trace_schema_version": self.source_trace_schema_version,
            "source_evaluation_id": self.source_evaluation_id,
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
            content_hash=data.get("content_hash"),
            applied_at=data.get("applied_at"),
            source_trace_schema_version=str(data.get("source_trace_schema_version") or "1.0"),
            source_evaluation_id=data.get("source_evaluation_id"),
        )
