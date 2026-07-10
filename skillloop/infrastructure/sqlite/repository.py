from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from skillloop.infrastructure.sqlite.migrations import SCHEMA_VERSION, apply_migrations
from skillloop.schema import AgentTrace, Evaluation, Proposal


class SQLiteRepository:
    """Low-level SQLite persistence for SkillLoop.

    Wraps all SQL, schema migrations, batching, pagination, and streaming I/O.
    The public :class:`~skillloop.store.SkillLoopStore` delegates to this repository
    and adds filesystem-side raw-trace preservation on top.

    TODO(WAL): WAL mode is intentionally not enabled yet. This is a single-writer
    local tool where all writes funnel through one controller tick / CLI process; the
    existing busy_timeout already absorbs concurrent readers, and WAL would trade a
    small write gain for checkpoint complexity and weaker crash durability on
    user-managed project directories. Revisit only if multi-process write contention
    is measured in practice.
    """

    def __init__(self, db_path: Path, root: Path) -> None:
        self.db_path = Path(db_path)
        self.root = Path(root)
        self._initialized = False

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(str(self.db_path), timeout=30)
        try:
            connection.execute("PRAGMA busy_timeout = 30000")
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Explicit transaction boundary. Commits on success, rolls back on error."""
        with self.connect() as conn, conn:
            yield conn

    def init(self) -> None:
        if self._initialized:
            return
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            apply_migrations(conn, target=SCHEMA_VERSION)
        self._initialized = True

    def _exec(self, conn: sqlite3.Connection | None, sql: str, params: tuple) -> None:
        if conn is None:
            with self.transaction() as c:
                c.execute(sql, params)
        else:
            conn.execute(sql, params)

    def save_trace(self, trace: AgentTrace, conn: sqlite3.Connection | None = None) -> str:
        payload = json.dumps(trace.to_dict(), ensure_ascii=False)
        self._exec(
            conn,
            "INSERT OR REPLACE INTO traces (id, source, created_at, payload) VALUES (?, ?, ?, ?)",
            (trace.id, trace.source, trace.created_at, payload),
        )
        return trace.id

    def save_traces(
        self, traces: list[AgentTrace], conn: sqlite3.Connection | None = None
    ) -> list[str]:
        records = [
            (t.id, t.source, t.created_at, json.dumps(t.to_dict(), ensure_ascii=False))
            for t in traces
        ]
        if conn is None:
            with self.transaction() as c:
                c.executemany(
                    "INSERT OR REPLACE INTO traces (id, source, created_at, payload) VALUES (?, ?, ?, ?)",
                    records,
                )
        else:
            conn.executemany(
                "INSERT OR REPLACE INTO traces (id, source, created_at, payload) VALUES (?, ?, ?, ?)",
                records,
            )
        return [t.id for t in traces]

    def get_trace_payload(
        self, trace_id: str, conn: sqlite3.Connection | None = None
    ) -> str | None:
        if conn is None:
            with self.connect() as c:
                row = c.execute("SELECT payload FROM traces WHERE id = ?", (trace_id,)).fetchone()
        else:
            row = conn.execute("SELECT payload FROM traces WHERE id = ?", (trace_id,)).fetchone()
        return row[0] if row is not None else None

    def iter_trace_payloads(
        self, limit: int | None = None, offset: int = 0, conn: sqlite3.Connection | None = None
    ) -> Iterator[str]:
        query = "SELECT payload FROM traces ORDER BY created_at DESC"
        args: tuple[int, ...] = ()
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            args = (int(limit), int(offset))
        if conn is None:
            with self.connect() as c:
                rows = c.execute(query, args).fetchall()
        else:
            rows = conn.execute(query, args).fetchall()
        for (payload,) in rows:
            yield payload

    def stream_export_traces(self, out_path: Path) -> int:
        """Write every trace payload to a JSONL file one line at a time."""
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with out_path.open("w", encoding="utf-8") as fh:
            for payload in self.iter_trace_payloads():
                fh.write(payload)
                fh.write("\n")
                count += 1
        return count

    def ingest_jsonl_traces(self, jsonl_path: Path, batch_size: int = 500) -> int:
        """Read a JSONL file line-by-line and insert traces in bounded batches."""
        jsonl_path = Path(jsonl_path)
        saved = 0
        batch: list[AgentTrace] = []
        with jsonl_path.open("r", encoding="utf-8") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if not line:
                    continue
                batch.append(AgentTrace.from_dict(json.loads(line)))
                if len(batch) >= batch_size:
                    self.save_traces(batch)
                    saved += len(batch)
                    batch.clear()
        if batch:
            self.save_traces(batch)
            saved += len(batch)
        return saved

    def save_evaluation(
        self, evaluation: Evaluation, conn: sqlite3.Connection | None = None
    ) -> str:
        payload = json.dumps(evaluation.to_dict(), ensure_ascii=False)
        self._exec(
            conn,
            "INSERT OR REPLACE INTO evaluations (id, trace_id, score, created_at, payload) VALUES (?, ?, ?, ?, ?)",
            (evaluation.id, evaluation.trace_id, evaluation.score, evaluation.created_at, payload),
        )
        return evaluation.id

    def save_evaluations(
        self, evaluations: list[Evaluation], conn: sqlite3.Connection | None = None
    ) -> list[str]:
        records = [
            (e.id, e.trace_id, e.score, e.created_at, json.dumps(e.to_dict(), ensure_ascii=False))
            for e in evaluations
        ]
        if conn is None:
            with self.transaction() as c:
                c.executemany(
                    "INSERT OR REPLACE INTO evaluations (id, trace_id, score, created_at, payload) VALUES (?, ?, ?, ?, ?)",
                    records,
                )
        else:
            conn.executemany(
                "INSERT OR REPLACE INTO evaluations (id, trace_id, score, created_at, payload) VALUES (?, ?, ?, ?, ?)",
                records,
            )
        return [e.id for e in evaluations]

    def list_evaluation_payloads(
        self,
        trace_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
        conn: sqlite3.Connection | None = None,
    ) -> list[str]:
        if trace_id is None:
            query = "SELECT payload FROM evaluations ORDER BY created_at DESC"
            args: tuple = ()
        else:
            query = "SELECT payload FROM evaluations WHERE trace_id = ? ORDER BY created_at DESC"
            args = (trace_id,)
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            args = args + (int(limit), int(offset))
        if conn is None:
            with self.connect() as c:
                rows = c.execute(query, args).fetchall()
        else:
            rows = conn.execute(query, args).fetchall()
        return [row[0] for row in rows]

    def latest_evaluation_payload(
        self, trace_id: str, conn: sqlite3.Connection | None = None
    ) -> str | None:
        if conn is None:
            with self.connect() as c:
                row = c.execute(
                    "SELECT payload FROM evaluations WHERE trace_id = ? ORDER BY created_at DESC LIMIT 1",
                    (trace_id,),
                ).fetchone()
        else:
            row = conn.execute(
                "SELECT payload FROM evaluations WHERE trace_id = ? ORDER BY created_at DESC LIMIT 1",
                (trace_id,),
            ).fetchone()
        return row[0] if row is not None else None

    def latest_evaluation_payloads(
        self, trace_ids: set[str] | None = None, conn: sqlite3.Connection | None = None
    ) -> dict[str, str]:
        query = "SELECT trace_id, payload FROM evaluations"
        args: tuple = ()
        if trace_ids is not None:
            if not trace_ids:
                return {}
            query += f" WHERE trace_id IN ({','.join('?' for _ in trace_ids)})"
            args = tuple(sorted(trace_ids))
        query += " ORDER BY trace_id, created_at DESC"
        if conn is None:
            with self.connect() as c:
                rows = c.execute(query, args).fetchall()
        else:
            rows = conn.execute(query, args).fetchall()
        latest: dict[str, str] = {}
        for trace_id, payload in rows:
            latest.setdefault(str(trace_id), payload)
        return latest

    def find_duplicate_proposal_payload(
        self, proposal: Proposal, active_statuses: set[str], conn: sqlite3.Connection | None = None
    ) -> str | None:
        if conn is None:
            with self.connect() as c:
                rows = c.execute(
                    "SELECT payload FROM proposals WHERE kind = ? AND content_hash = ? AND status IN ("
                    + ",".join("?" for _ in sorted(active_statuses))
                    + ")",
                    (proposal.kind, proposal.content_hash, *sorted(active_statuses)),
                ).fetchall()
        else:
            rows = conn.execute(
                "SELECT payload FROM proposals WHERE kind = ? AND content_hash = ? AND status IN ("
                + ",".join("?" for _ in sorted(active_statuses))
                + ")",
                (proposal.kind, proposal.content_hash, *sorted(active_statuses)),
            ).fetchall()
        for (payload,) in rows:
            existing = Proposal.from_dict(json.loads(payload))
            if existing.id != proposal.id:
                return payload
        return None

    def save_proposal(self, proposal: Proposal, conn: sqlite3.Connection | None = None) -> str:
        payload = json.dumps(proposal.to_dict(), ensure_ascii=False)
        self._exec(
            conn,
            "INSERT OR REPLACE INTO proposals (id, trace_id, kind, status, content_hash, created_at, payload) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                proposal.id,
                proposal.trace_id,
                proposal.kind,
                proposal.status,
                proposal.content_hash,
                proposal.created_at,
                payload,
            ),
        )
        return proposal.id

    def save_proposals(
        self, proposals: list[Proposal], conn: sqlite3.Connection | None = None
    ) -> list[str]:
        records = [
            (
                p.id,
                p.trace_id,
                p.kind,
                p.status,
                p.content_hash,
                p.created_at,
                json.dumps(p.to_dict(), ensure_ascii=False),
            )
            for p in proposals
        ]
        if conn is None:
            with self.transaction() as c:
                c.executemany(
                    "INSERT OR REPLACE INTO proposals (id, trace_id, kind, status, content_hash, created_at, payload) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    records,
                )
        else:
            conn.executemany(
                "INSERT OR REPLACE INTO proposals (id, trace_id, kind, status, content_hash, created_at, payload) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                records,
            )
        return [p.id for p in proposals]

    def list_proposal_payloads(
        self,
        status: str | None = None,
        limit: int | None = None,
        offset: int = 0,
        conn: sqlite3.Connection | None = None,
    ) -> list[str]:
        if status is None:
            query = "SELECT payload FROM proposals ORDER BY created_at DESC"
            args: tuple = ()
        else:
            query = "SELECT payload FROM proposals WHERE status = ? ORDER BY created_at DESC"
            args = (status,)
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            args = args + (int(limit), int(offset))
        if conn is None:
            with self.connect() as c:
                rows = c.execute(query, args).fetchall()
        else:
            rows = conn.execute(query, args).fetchall()
        return [row[0] for row in rows]

    def get_proposal_payload(
        self, proposal_id: str, conn: sqlite3.Connection | None = None
    ) -> str | None:
        if conn is None:
            with self.connect() as c:
                row = c.execute(
                    "SELECT payload FROM proposals WHERE id = ?", (proposal_id,)
                ).fetchone()
        else:
            row = conn.execute(
                "SELECT payload FROM proposals WHERE id = ?", (proposal_id,)
            ).fetchone()
        return row[0] if row is not None else None

    def save_controller_run(self, report: dict, conn: sqlite3.Connection | None = None) -> str:
        run_id = str(report["id"])
        payload = json.dumps(report, ensure_ascii=False)
        self._exec(
            conn,
            "INSERT OR REPLACE INTO controller_runs (id, started_at, finished_at, payload) VALUES (?, ?, ?, ?)",
            (run_id, str(report["started_at"]), report.get("finished_at"), payload),
        )
        return run_id

    def list_controller_run_payloads(
        self, limit: int | None = None, offset: int = 0, conn: sqlite3.Connection | None = None
    ) -> list[str]:
        query = "SELECT payload FROM controller_runs ORDER BY started_at DESC"
        args: tuple = ()
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            args = (int(limit), int(offset))
        if conn is None:
            with self.connect() as c:
                rows = c.execute(query, args).fetchall()
        else:
            rows = conn.execute(query, args).fetchall()
        return [row[0] for row in rows]

    def get_controller_run_payload(
        self, run_id: str, conn: sqlite3.Connection | None = None
    ) -> str | None:
        if conn is None:
            with self.connect() as c:
                row = c.execute(
                    "SELECT payload FROM controller_runs WHERE id = ?", (run_id,)
                ).fetchone()
                if row is None:
                    row = self._run_prefix_match(c, run_id)
        else:
            row = conn.execute(
                "SELECT payload FROM controller_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if row is None:
                row = self._run_prefix_match(conn, run_id)
        return row[0] if row is not None else None

    @staticmethod
    def _run_prefix_match(conn: sqlite3.Connection, run_id: str):
        escaped_id = run_id.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        rows = conn.execute(
            "SELECT payload FROM controller_runs WHERE id LIKE ? ESCAPE '\\' ORDER BY started_at DESC",
            (f"{escaped_id}%",),
        ).fetchall()
        if len(rows) == 1:
            return rows[0]
        if len(rows) > 1:
            raise KeyError(f"controller run id prefix is ambiguous: {run_id}")
        return None
