from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from skillloop.provenance import component_provenance
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
        result.component_provenance = component_provenance(
            kind="evaluator",
            name=evaluator.name,
            version=evaluator.version,
            func=evaluator.evaluate,
            extra={"description": evaluator.description},
        )
        result.artifact_sha256 = result.compute_artifact_sha256()
        return result


def default_evaluator_registry() -> EvaluatorRegistry:
    from skillloop.eval.legacy import EVALUATOR_NAME as LEGACY_NAME
    from skillloop.eval.legacy import EVALUATOR_VERSION as LEGACY_VERSION
    from skillloop.eval.legacy import evaluate_trace as evaluate_legacy_trace
    from skillloop.eval.rubric import EVALUATOR_NAME, EVALUATOR_VERSION, evaluate_trace

    registry = EvaluatorRegistry()
    registry.register(
        RegisteredEvaluator(
            name=LEGACY_NAME,
            version=LEGACY_VERSION,
            evaluate=evaluate_legacy_trace,
            description="Legacy lexical rubric used only for replay/benchmark comparisons.",
        )
    )
    registry.register(
        RegisteredEvaluator(
            name=EVALUATOR_NAME,
            version=EVALUATOR_VERSION,
            evaluate=evaluate_trace,
            description="Deterministic rubric evaluator with structured trace/tool/user evidence.",
        )
    )
    return registry
