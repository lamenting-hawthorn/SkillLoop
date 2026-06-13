from __future__ import annotations

import json
import sqlite3
import shutil
from pathlib import Path

from skillloop.schema import AgentTrace, Evaluation, Proposal, sha256_text


class SkillLoopStore:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.state_dir = self.root / ".skillloop"
        self.db_path = self.state_dir / "skillloop.db"
        self.raw_trace_dir = self.state_dir / "raw_traces"

    def init(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS traces (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evaluations (
                    id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS proposals (
                    id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS controller_runs (
                    id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    payload TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def save_trace(self, trace: AgentTrace) -> str:
        self.init()
        self._preserve_raw_trace(trace)
        trace.normalized_trace_sha256 = trace.compute_normalized_sha256()
        payload = json.dumps(trace.to_dict(), ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO traces (id, source, created_at, payload) VALUES (?, ?, ?, ?)",
                (trace.id, trace.source, trace.created_at, payload),
            )
        return trace.id

    def _preserve_raw_trace(self, trace: AgentTrace) -> None:
        if not trace.raw_artifact_ref:
            return
        raw_path = Path(trace.raw_artifact_ref).expanduser()
        if not raw_path.exists() or not raw_path.is_file():
            return
        raw_bytes = raw_path.read_bytes()
        trace.raw_trace_sha256 = trace.raw_trace_sha256 or sha256_text(raw_bytes.decode("utf-8", errors="replace"))
        self.raw_trace_dir.mkdir(parents=True, exist_ok=True)
        suffix = raw_path.suffix or ".raw"
        preserved = self.raw_trace_dir / f"{trace.id}{suffix}"
        if raw_path.resolve() != preserved.resolve():
            shutil.copyfile(raw_path, preserved)
        trace.raw_artifact_ref = str(preserved.relative_to(self.root))

    def read_preserved_raw_trace(self, trace: AgentTrace | str) -> str:
        trace_obj = self.get_trace(trace) if isinstance(trace, str) else trace
        if not trace_obj.raw_artifact_ref:
            raise FileNotFoundError(f"trace has no preserved raw artifact: {trace_obj.id}")
        raw_path = (self.root / trace_obj.raw_artifact_ref).resolve()
        raw_path.relative_to(self.root)
        return raw_path.read_text(encoding="utf-8")

    def get_trace(self, trace_id: str) -> AgentTrace:
        self.init()
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM traces WHERE id = ?", (trace_id,)).fetchone()
        if row is None:
            raise KeyError(f"trace not found: {trace_id}")
        return AgentTrace.from_dict(json.loads(row[0]))

    def list_traces(self) -> list[AgentTrace]:
        self.init()
        with self._connect() as conn:
            rows = conn.execute("SELECT payload FROM traces ORDER BY created_at DESC").fetchall()
        return [AgentTrace.from_dict(json.loads(row[0])) for row in rows]

    def save_evaluation(self, evaluation: Evaluation) -> str:
        self.init()
        evaluation.artifact_sha256 = evaluation.compute_artifact_sha256()
        payload = json.dumps(evaluation.to_dict(), ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO evaluations (id, trace_id, score, created_at, payload) VALUES (?, ?, ?, ?, ?)",
                (evaluation.id, evaluation.trace_id, evaluation.score, evaluation.created_at, payload),
            )
        return evaluation.id

    def list_evaluations(self, trace_id: str | None = None) -> list[Evaluation]:
        self.init()
        if trace_id is None:
            query = "SELECT payload FROM evaluations ORDER BY created_at DESC"
            args: tuple[str, ...] = ()
        else:
            query = "SELECT payload FROM evaluations WHERE trace_id = ? ORDER BY created_at DESC"
            args = (trace_id,)
        with self._connect() as conn:
            rows = conn.execute(query, args).fetchall()
        payloads = [json.loads(row[0]) for row in rows]
        return [Evaluation.from_dict(p) for p in payloads]

    def latest_evaluation(self, trace_id: str) -> Evaluation | None:
        evaluations = self.list_evaluations(trace_id)
        return evaluations[0] if evaluations else None

    def find_duplicate_proposal(self, proposal: Proposal) -> Proposal | None:
        active_statuses = {"pending", "approved", "applied"}
        for existing in self.list_proposals(status=None):
            if existing.id == proposal.id:
                continue
            if existing.kind == proposal.kind and existing.content_hash == proposal.content_hash and existing.status in active_statuses:
                return existing
        return None

    def save_proposal(self, proposal: Proposal) -> str:
        self.init()
        duplicate = self.find_duplicate_proposal(proposal)
        if duplicate is not None and duplicate.id != proposal.id:
            return duplicate.id
        payload = json.dumps(proposal.to_dict(), ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO proposals (id, trace_id, kind, status, created_at, payload) VALUES (?, ?, ?, ?, ?, ?)",
                (proposal.id, proposal.trace_id, proposal.kind, proposal.status, proposal.created_at, payload),
            )
        return proposal.id

    def list_proposals(self, status: str | None = None) -> list[Proposal]:
        self.init()
        if status is None:
            query = "SELECT payload FROM proposals ORDER BY created_at DESC"
            args: tuple[str, ...] = ()
        else:
            query = "SELECT payload FROM proposals WHERE status = ? ORDER BY created_at DESC"
            args = (status,)
        with self._connect() as conn:
            rows = conn.execute(query, args).fetchall()
        return [Proposal.from_dict(json.loads(row[0])) for row in rows]

    def get_proposal(self, proposal_id: str) -> Proposal:
        self.init()
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM proposals WHERE id = ?", (proposal_id,)).fetchone()
        if row is None:
            raise KeyError(f"proposal not found: {proposal_id}")
        return Proposal.from_dict(json.loads(row[0]))

    def save_controller_run(self, report: dict) -> str:
        self.init()
        run_id = str(report["id"])
        payload = json.dumps(report, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO controller_runs (id, started_at, finished_at, payload) VALUES (?, ?, ?, ?)",
                (run_id, str(report.get("started_at") or ""), report.get("finished_at"), payload),
            )
        return run_id

    def list_controller_runs(self, limit: int | None = None) -> list[dict]:
        self.init()
        query = "SELECT payload FROM controller_runs ORDER BY started_at DESC"
        args: tuple[int, ...] = ()
        if limit is not None:
            query += " LIMIT ?"
            args = (int(limit),)
        with self._connect() as conn:
            rows = conn.execute(query, args).fetchall()
        return [json.loads(row[0]) for row in rows]

    def get_controller_run(self, run_id: str) -> dict:
        self.init()
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM controller_runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                rows = conn.execute(
                    "SELECT payload FROM controller_runs WHERE id LIKE ? ORDER BY started_at DESC",
                    (f"{run_id}%",),
                ).fetchall()
                if len(rows) == 1:
                    row = rows[0]
                elif len(rows) > 1:
                    raise KeyError(f"controller run id prefix is ambiguous: {run_id}")
        if row is None:
            raise KeyError(f"controller run not found: {run_id}")
        return json.loads(row[0])
