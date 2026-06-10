from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from skillloop.schema import Evaluation

CONDITION_VERSION = "1.0"


@dataclass(frozen=True)
class LoopConditionResult:
    passed: bool
    should_continue: bool
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "should_continue": self.should_continue,
            "reasons": self.reasons,
        }


@dataclass(frozen=True)
class LoopCondition:
    """Declarative done/continuation condition for a loop evaluation.

    `passed` means the trace satisfies the done condition.
    `should_continue` means the loop may keep improving/evaluating later.
    A max_iterations breach is fail-closed: not passed, but should_continue=False.
    """

    score_gte: int = 70
    required_tags: tuple[str, ...] = ()
    forbidden_tags: tuple[str, ...] = ()
    max_iterations: int | None = None
    version: str = CONDITION_VERSION

    def __post_init__(self) -> None:
        if self.max_iterations is not None and int(self.max_iterations) < 1:
            raise ValueError("max_iterations must be >= 1")
        object.__setattr__(self, "score_gte", int(self.score_gte))
        object.__setattr__(self, "required_tags", tuple(str(tag) for tag in self.required_tags if str(tag)))
        object.__setattr__(self, "forbidden_tags", tuple(str(tag) for tag in self.forbidden_tags if str(tag)))
        object.__setattr__(self, "max_iterations", int(self.max_iterations) if self.max_iterations is not None else None)

    def evaluate(self, evaluation: Evaluation, *, prior_iterations: int = 0) -> LoopConditionResult:
        reasons: list[str] = []
        should_continue = True
        if self.max_iterations is not None and prior_iterations >= self.max_iterations:
            reasons.append(f"max_iterations_exceeded:{prior_iterations}>={self.max_iterations}")
            should_continue = False

        if evaluation.score < self.score_gte:
            reasons.append(f"score_below_threshold:{evaluation.score}<{self.score_gte}")

        tags = set(evaluation.tags)
        for tag in self.required_tags:
            if tag not in tags:
                reasons.append(f"missing_required_tag:{tag}")
        for tag in self.forbidden_tags:
            if tag in tags:
                reasons.append(f"forbidden_tag_present:{tag}")

        passed = not reasons
        return LoopConditionResult(passed=passed, should_continue=should_continue, reasons=reasons)

    def annotate(self, evaluation: Evaluation, *, prior_iterations: int = 0) -> LoopConditionResult:
        result = self.evaluate(evaluation, prior_iterations=prior_iterations)
        evaluation.run_condition = {
            "version": self.version,
            "condition": self.to_dict(),
            "result": result.to_dict(),
            "prior_iterations": prior_iterations,
        }
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "score_gte": self.score_gte,
            "required_tags": list(self.required_tags),
            "forbidden_tags": list(self.forbidden_tags),
            "max_iterations": self.max_iterations,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "LoopCondition":
        data = dict(data or {})
        return cls(
            version=str(data.get("version") or CONDITION_VERSION),
            score_gte=int(data.get("score_gte", data.get("min_score", 70))),
            required_tags=tuple(str(tag) for tag in data.get("required_tags", [])),
            forbidden_tags=tuple(str(tag) for tag in data.get("forbidden_tags", [])),
            max_iterations=data.get("max_iterations"),
        )

    @classmethod
    def from_json(cls, text: str | None) -> "LoopCondition":
        if not text:
            return cls()
        return cls.from_dict(json.loads(text))
