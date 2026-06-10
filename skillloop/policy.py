from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from skillloop.conditions import LoopCondition

POLICY_VERSION = "1.0"


@dataclass
class IngestionPolicy:
    enabled: bool = False
    adapter: str = "none"
    paths: list[str] = field(default_factory=list)
    hermes_db_path: str | None = None
    latest: bool = False
    max_sessions: int = 20

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "IngestionPolicy":
        data = dict(data or {})
        return cls(
            enabled=bool(data.get("enabled", False)),
            adapter=str(data.get("adapter") or "none"),
            paths=[str(path) for path in data.get("paths", [])],
            hermes_db_path=data.get("hermes_db_path"),
            latest=bool(data.get("latest", False)),
            max_sessions=int(data.get("max_sessions", 20)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "adapter": self.adapter,
            "paths": self.paths,
            "hermes_db_path": self.hermes_db_path,
            "latest": self.latest,
            "max_sessions": self.max_sessions,
        }


@dataclass
class EvaluationPolicy:
    evaluator: str = "rubric"
    min_score: int = 70
    only_unevaluated: bool = True
    distill_failures: bool = True
    limit: int | None = None
    condition: LoopCondition = field(default_factory=LoopCondition)

    def __post_init__(self) -> None:
        if not isinstance(self.condition, LoopCondition):
            self.condition = LoopCondition.from_dict(dict(self.condition or {}))
        self.min_score = int(self.min_score)
        if self.condition.score_gte != self.min_score:
            self.condition = LoopCondition(
                score_gte=self.min_score,
                required_tags=self.condition.required_tags,
                forbidden_tags=self.condition.forbidden_tags,
                max_iterations=self.condition.max_iterations,
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "EvaluationPolicy":
        data = dict(data or {})
        min_score = int(data.get("min_score", 70))
        return cls(
            evaluator=str(data.get("evaluator") or "rubric"),
            min_score=min_score,
            only_unevaluated=bool(data.get("only_unevaluated", True)),
            distill_failures=bool(data.get("distill_failures", True)),
            limit=data.get("limit"),
            condition=LoopCondition.from_dict(data.get("condition") or {"score_gte": min_score}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluator": self.evaluator,
            "min_score": self.min_score,
            "only_unevaluated": self.only_unevaluated,
            "distill_failures": self.distill_failures,
            "limit": self.limit,
            "condition": self.condition.to_dict(),
        }


@dataclass
class DatasetPolicy:
    enabled: bool = False
    kind: str = "sft"
    out: str = "data/sft.jsonl"
    min_score: int = 70
    splits: str = "train=0.8,validation=0.1,test=0.1"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "DatasetPolicy":
        data = dict(data or {})
        return cls(
            enabled=bool(data.get("enabled", False)),
            kind=str(data.get("kind") or "sft"),
            out=str(data.get("out") or "data/sft.jsonl"),
            min_score=int(data.get("min_score", 70)),
            splits=str(data.get("splits") or "train=0.8,validation=0.1,test=0.1"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "kind": self.kind,
            "out": self.out,
            "min_score": self.min_score,
            "splits": self.splits,
        }


@dataclass
class TrainingPolicy:
    auto_plan: bool = False
    auto_run: bool = False
    require_approval: bool = True
    target: str = "axolotl"
    base_model: str = ""
    max_cost_usd: float | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "TrainingPolicy":
        data = dict(data or {})
        max_cost = data.get("max_cost_usd")
        return cls(
            auto_plan=bool(data.get("auto_plan", False)),
            auto_run=bool(data.get("auto_run", False)),
            require_approval=bool(data.get("require_approval", True)),
            target=str(data.get("target") or "axolotl"),
            base_model=str(data.get("base_model") or ""),
            max_cost_usd=float(max_cost) if max_cost is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "auto_plan": self.auto_plan,
            "auto_run": self.auto_run,
            "require_approval": self.require_approval,
            "target": self.target,
            "base_model": self.base_model,
            "max_cost_usd": self.max_cost_usd,
        }


@dataclass
class SkillLoopPolicy:
    version: str = POLICY_VERSION
    mode: str = "autonomous_review_first"
    ingestion: IngestionPolicy = field(default_factory=IngestionPolicy)
    evaluation: EvaluationPolicy = field(default_factory=EvaluationPolicy)
    dataset: DatasetPolicy = field(default_factory=DatasetPolicy)
    training: TrainingPolicy = field(default_factory=TrainingPolicy)

    @classmethod
    def default(cls) -> "SkillLoopPolicy":
        return cls()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SkillLoopPolicy":
        return cls(
            version=str(data.get("version") or POLICY_VERSION),
            mode=str(data.get("mode") or "autonomous_review_first"),
            ingestion=IngestionPolicy.from_dict(data.get("ingestion")),
            evaluation=EvaluationPolicy.from_dict(data.get("evaluation")),
            dataset=DatasetPolicy.from_dict(data.get("dataset")),
            training=TrainingPolicy.from_dict(data.get("training")),
        )

    @classmethod
    def load(cls, path: str | Path) -> "SkillLoopPolicy":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def save(self, path: str | Path) -> Path:
        out = Path(path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "mode": self.mode,
            "ingestion": self.ingestion.to_dict(),
            "evaluation": self.evaluation.to_dict(),
            "dataset": self.dataset.to_dict(),
            "training": self.training.to_dict(),
        }
