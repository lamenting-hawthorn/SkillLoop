from __future__ import annotations

import json
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from skillloop.fs_safety import (
    ensure_not_symlink_escape,
    resolve_under_root,
    safe_path_segment,
    sha256_bytes,
)
from skillloop.infrastructure.sqlite.migrations import SCHEMA_VERSION
from skillloop.infrastructure.sqlite.repository import SQLiteRepository
from skillloop.schema import AgentTrace, Evaluation, Proposal, SCHEMA_VERSION as SCHEMA_VERSION_CONST

SCHEMA_VERSION = SCHEMA_VERSION_CONST


class SkillLoopStore:
    """Public persistence API for SkillLoop.

    Backward-compatible facade over :class:`~skillloop.infrastructure.sqlite.repository.SQLiteRepository`.
    Raw trace preservation (filesystem side effects) lives here; all SQL is delegated
    to the repository. New callers may use the repository directly for batch/streaming ops.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.state_dir = self.root / ".skillloop"
        self.db_path = self.state_dir / "skillloop.db"
        self.raw_trace_dir = self.state_dir / "raw_traces"
        self._repo = SQLiteRepository(self.db_path, self.root)
        self._active_conn = None

    def init(self) -> None:
        ensure_not_symlink_escape(self.state_dir, self.root, label="state directory")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        ensure_not_symlink_escape(self.state_dir, self.root, label="state directory")
        self._repo.init()

    @contextmanager
    def transaction(self) -> Iterator["SkillLoopStore"]:
        """Explicit transaction boundary spanning controller ticks and batch writes.

        All persistence calls made while inside the context reuse one connection, so
        the whole tick commits atomically or rolls back on error.
        """
        self.init()
        with self._repo.transaction() as conn:
            self._active_conn = conn
            try:
                yield self
            finally:
                self._active_conn = None

    def save_trace(self, trace: AgentTrace) -> str:
        self.init()
        self._preserve_raw_trace(trace)
        trace.normalized_trace_sha256 = trace.compute_normalized_sha256()
        return self._repo.save_trace(trace, self._active_conn)

    def save_traces(self, traces: list[AgentTrace]) -> list[str]:
        self.init()
        for trace in traces:
            self._preserve_raw_trace(trace)
            trace.normalized_trace_sha256 = trace.compute_normalized_sha256()
        return self._repo.save_traces(traces, self._active_conn)

    def _preserve_raw_trace(self, trace: AgentTrace) -> None:
        if not trace.raw_artifact_ref:
            return
        raw_path = Path(trace.raw_artifact_ref).expanduser()
        if not raw_path.exists() or not raw_path.is_file():
            return
        trace_id = safe_path_segment(trace.id, label="trace id")
        raw_bytes = raw_path.read_bytes()
        trace.raw_trace_sha256 = trace.raw_trace_sha256 or sha256_bytes(raw_bytes)
        ensure_not_symlink_escape(self.raw_trace_dir, self.state_dir, label="raw trace directory")
        self.raw_trace_dir.mkdir(parents=True, exist_ok=True)
        ensure_not_symlink_escape(self.raw_trace_dir, self.state_dir, label="raw trace directory")
        suffix = raw_path.suffix or ".raw"
        preserved = ensure_not_symlink_escape(
            self.raw_trace_dir / f"{trace_id}{suffix}", self.raw_trace_dir, label="preserved raw trace"
        )
        if raw_path.resolve() != preserved.resolve():
            shutil.copyfile(raw_path, preserved)
        trace.raw_artifact_ref = str(preserved.relative_to(self.root))

    def read_preserved_raw_trace(self, trace: AgentTrace | str) -> str:
        trace_obj = self.get_trace(trace) if isinstance(trace, str) else trace
        if not trace_obj.raw_artifact_ref:
            raise FileNotFoundError(f"trace has no preserved raw artifact: {trace_obj.id}")
        ensure_not_symlink_escape(self.raw_trace_dir, self.state_dir, label="raw trace directory")
        raw_path = resolve_under_root(self.root, trace_obj.raw_artifact_ref, label="preserved raw trace")
        try:
            raw_path.relative_to(self.raw_trace_dir.resolve())
        except ValueError as exc:
            raise ValueError(f"preserved raw trace must stay under {self.raw_trace_dir}") from exc
        ensure_not_symlink_escape(raw_path, self.raw_trace_dir, label="preserved raw trace")
        return raw_path.read_text(encoding="utf-8")

    def get_trace(self, trace_id: str) -> AgentTrace:
        self.init()
        payload = self._repo.get_trace_payload(trace_id, self._active_conn)
        if payload is None:
            raise KeyError(f"trace not found: {trace_id}")
        return AgentTrace.from_dict(json.loads(payload))

    def list_traces(self, limit: int | None = None, offset: int = 0) -> list[AgentTrace]:
        self.init()
        return [
            AgentTrace.from_dict(json.loads(p))
            for p in self._repo.iter_trace_payloads(limit, offset, self._active_conn)
        ]

    def ingest_jsonl_traces(self, jsonl_path: str | Path, batch_size: int = 500) -> int:
        """Stream a JSONL file of trace records into the store without loading it all at once."""
        self.init()
        return self._repo.ingest_jsonl_traces(Path(jsonl_path), batch_size=batch_size)

    def stream_export_traces(self, out_path: str | Path) -> int:
        """Stream all traces out to a JSONL file without buffering the full set in memory."""
        self.init()
        return self._repo.stream_export_traces(Path(out_path))

    def save_evaluation(self, evaluation: Evaluation) -> str:
        self.init()
        evaluation.artifact_sha256 = evaluation.compute_artifact_sha256()
        return self._repo.save_evaluation(evaluation, self._active_conn)

    def save_evaluations(self, evaluations: list[Evaluation]) -> list[str]:
        self.init()
        for evaluation in evaluations:
            evaluation.artifact_sha256 = evaluation.compute_artifact_sha256()
        return self._repo.save_evaluations(evaluations, self._active_conn)

    def list_evaluations(
        self, trace_id: str | None = None, limit: int | None = None, offset: int = 0
    ) -> list[Evaluation]:
        self.init()
        payloads = self._repo.list_evaluation_payloads(trace_id, limit, offset, self._active_conn)
        return [Evaluation.from_dict(json.loads(p)) for p in payloads]

    def latest_evaluation(self, trace_id: str) -> Evaluation | None:
        self.init()
        payload = self._repo.latest_evaluation_payload(trace_id, self._active_conn)
        return Evaluation.from_dict(json.loads(payload)) if payload is not None else None

    def latest_evaluations(self, trace_ids: set[str] | None = None) -> dict[str, Evaluation]:
        self.init()
        payloads = self._repo.latest_evaluation_payloads(trace_ids, self._active_conn)
        return {tid: Evaluation.from_dict(json.loads(p)) for tid, p in payloads.items()}

    def find_duplicate_proposal(self, proposal: Proposal) -> Proposal | None:
        active_statuses = {"pending", "approved", "applied"}
        self.init()
        payload = self._repo.find_duplicate_proposal_payload(proposal, active_statuses, self._active_conn)
        return Proposal.from_dict(json.loads(payload)) if payload is not None else None

    def save_proposal(self, proposal: Proposal) -> str:
        self.init()
        duplicate = self.find_duplicate_proposal(proposal)
        if duplicate is not None and duplicate.id != proposal.id:
            return duplicate.id
        return self._repo.save_proposal(proposal, self._active_conn)

    def save_proposals(self, proposals: list[Proposal]) -> list[str]:
        self.init()
        kept: list[Proposal] = []
        for proposal in proposals:
            duplicate = self.find_duplicate_proposal(proposal)
            if duplicate is None or duplicate.id == proposal.id:
                kept.append(proposal)
        return self._repo.save_proposals(kept, self._active_conn)

    def list_proposals(
        self, status: str | None = None, limit: int | None = None, offset: int = 0
    ) -> list[Proposal]:
        self.init()
        payloads = self._repo.list_proposal_payloads(status, limit, offset, self._active_conn)
        return [Proposal.from_dict(json.loads(p)) for p in payloads]

    def get_proposal(self, proposal_id: str) -> Proposal:
        self.init()
        payload = self._repo.get_proposal_payload(proposal_id, self._active_conn)
        if payload is None:
            raise KeyError(f"proposal not found: {proposal_id}")
        return Proposal.from_dict(json.loads(payload))

    def save_controller_run(self, report: dict) -> str:
        self.init()
        if not report.get("id"):
            raise ValueError("report must have non-empty 'id'")
        if not report.get("started_at"):
            raise ValueError("report must have non-empty 'started_at'")
        return self._repo.save_controller_run(report, self._active_conn)

    def list_controller_runs(self, limit: int | None = None, offset: int = 0) -> list[dict]:
        self.init()
        return [json.loads(p) for p in self._repo.list_controller_run_payloads(limit, offset, self._active_conn)]

    def get_controller_run(self, run_id: str) -> dict:
        self.init()
        payload = self._repo.get_controller_run_payload(run_id, self._active_conn)
        if payload is None:
            raise KeyError(f"controller run not found: {run_id}")
        return json.loads(payload)
