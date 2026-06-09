from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from skillloop.schema import AgentTrace, Evaluation

TraceEvaluator = Callable[[AgentTrace], Evaluation]


@dataclass(frozen=True)
class RegisteredEvaluator:
    name: str
    version: str
    evaluate: TraceEvaluator
    description: str = ""


class EvaluatorRegistry:
    def __init__(self) -> None:
        self._evaluators: dict[str, RegisteredEvaluator] = {}

    def register(self, evaluator: RegisteredEvaluator) -> None:
        if not evaluator.name:
            raise ValueError("evaluator name is required")
        self._evaluators[evaluator.name] = evaluator

    def names(self) -> list[str]:
        return sorted(self._evaluators)

    def get(self, name: str) -> RegisteredEvaluator:
        try:
            return self._evaluators[name]
        except KeyError as exc:
            raise KeyError(f"unknown evaluator: {name}") from exc

    def evaluate(self, trace: AgentTrace, name: str = "rubric") -> Evaluation:
        evaluator = self.get(name)
        result = evaluator.evaluate(trace)
        if result.evaluator_name in {"", "unknown"}:
            result.evaluator_name = evaluator.name
        if result.evaluator_version in {"", "0"}:
            result.evaluator_version = evaluator.version
        return result


def default_evaluator_registry() -> EvaluatorRegistry:
    from skillloop.eval.rubric import EVALUATOR_NAME, EVALUATOR_VERSION, evaluate_trace

    registry = EvaluatorRegistry()
    registry.register(
        RegisteredEvaluator(
            name=EVALUATOR_NAME,
            version=EVALUATOR_VERSION,
            evaluate=evaluate_trace,
            description="Deterministic rubric evaluator with structured trace/tool/user evidence.",
        )
    )
    return registry
