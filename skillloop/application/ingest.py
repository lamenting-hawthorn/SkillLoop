from __future__ import annotations

from typing import Optional

from skillloop.adapters.generic_jsonl import load_generic_jsonl
from skillloop.adapters.hermes import load_hermes_export, load_hermes_state_db
from skillloop.schema import AgentTrace
from skillloop.store import SkillLoopStore

from .requests import IngestionRequest


class IngestionService:
    def __init__(self, store: SkillLoopStore) -> None:
        self._store = store

    def ingest(self, req: IngestionRequest) -> tuple[AgentTrace, str]:
        if req.adapter == "generic":
            if req.input is None:
                raise SystemExit("generic ingest requires an input JSONL path")
            trace = load_generic_jsonl(req.input)
        elif req.adapter == "hermes":
            if req.input is None:
                raise SystemExit("hermes ingest requires an input JSON path")
            trace = load_hermes_export(req.input)
        elif req.adapter == "hermes-db":
            trace = load_hermes_state_db(req.db_path, session_id=req.session_id, latest=req.latest)
        else:
            raise SystemExit(f"Unsupported adapter: {req.adapter}")
        trace_id = self._store.save_trace(trace)
        return trace, trace_id


__all__ = ["IngestionService"]
