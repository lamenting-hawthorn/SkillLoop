from __future__ import annotations

from skillloop.eval.registry import default_evaluator_registry
from skillloop.schema import AgentTrace, Evaluation
from skillloop.store import SkillLoopStore


class EvaluationService:
    def __init__(self, store: SkillLoopStore) -> None:
        self._store = store

    def evaluate(self, trace: AgentTrace, evaluator: str) -> Evaluation:
        registry = default_evaluator_registry()
        evaluation = registry.evaluate(trace, name=evaluator)
        self._store.save_evaluation(evaluation)
        return evaluation


__all__ = ["EvaluationService"]
