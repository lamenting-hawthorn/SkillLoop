from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from skillloop.schema import AgentTrace, Evaluation, Proposal


class SkillLoopStore:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.state_dir = self.root / ".skillloop"
        self.db_path = self.state_dir / "skillloop.db"

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

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def save_trace(self, trace: AgentTrace) -> str:
        self.init()
        payload = json.dumps(trace.to_dict(), ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO traces (id, source, created_at, payload) VALUES (?, ?, ?, ?)",
                (trace.id, trace.source, trace.created_at, payload),
            )
        return trace.id

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
        return [Evaluation(trace_id=p["trace_id"], score=p["score"], tags=p.get("tags", []), notes=p.get("notes", []), id=p["id"], created_at=p["created_at"]) for p in payloads]

    def save_proposal(self, proposal: Proposal) -> str:
        self.init()
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
