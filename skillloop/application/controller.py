from __future__ import annotations

from dataclasses import dataclass

from skillloop.conditions import LoopCondition
from skillloop.controller import controller_tick
from skillloop.policy import DatasetPolicy, IngestionPolicy, SkillLoopPolicy
from skillloop.store import SkillLoopStore

from ._shared import load_policy
from .requests import SetupRequest


@dataclass
class SetupResult:
    policy_path: str
    report: object | None


class ControllerService:
    def __init__(self, store: SkillLoopStore) -> None:
        self._store = store

    def setup(self, req: SetupRequest) -> SetupResult:
        if req.connect != "hermes":
            raise SystemExit(f"Unsupported setup connector: {req.connect}")
        if req.max_sessions <= 0:
            raise SystemExit("--max-sessions must be positive")
        if not 0 <= req.min_score <= 100:
            raise SystemExit("--min-score must be between 0 and 100")
        policy = SkillLoopPolicy.default()
        policy.ingestion = IngestionPolicy(
            enabled=True,
            adapter="hermes-db",
            hermes_db_path=str(req.db_path),
            latest=False,
            max_sessions=req.max_sessions,
        )
        policy.dataset = DatasetPolicy(
            enabled=req.auto_export,
            auto_update=req.auto_export,
            kind="sft",
            out=req.dataset_out,
            min_score=req.min_score,
        )
        policy.evaluation.min_score = req.min_score
        policy.evaluation.condition = LoopCondition(score_gte=req.min_score)
        policy_path = policy.save(self._store.state_dir / "policy.json")
        report = None
        if req.start:
            report = controller_tick(self._store, policy)
        return SetupResult(policy_path=str(policy_path), report=report)

    def run(self) -> object:
        return controller_tick(self._store, load_policy(self._store))

    def history(self, limit: int | None) -> list[dict]:
        return self._store.list_controller_runs(limit=limit)

    def show(self, run_id: str) -> dict:
        try:
            return self._store.get_controller_run(run_id)
        except KeyError as exc:
            raise SystemExit(str(exc)) from exc


__all__ = ["ControllerService", "SetupResult"]
