from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from skillloop.conditions import LoopCondition
from skillloop.errors import InputError, PolicyError
from skillloop.sanitize import MAX_FIELD_CHARS, validate_field_size

POLICY_VERSION = "1.0"

SUPPORTED_INGESTION_ADAPTERS = frozenset({"none", "generic", "hermes-db"})
SUPPORTED_DATASET_KINDS = frozenset({"sft", "dpo"})
SUPPORTED_TRAINING_TARGETS = frozenset({"axolotl"})
SUPPORTED_MODES = frozenset({"autonomous_review_first", "manual", "autonomous"})
SUPPORTED_EVALUATORS = frozenset({"rubric", "llm_judge", "none"})


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
        adapter = str(data.get("adapter") or "none")
        if adapter not in SUPPORTED_INGESTION_ADAPTERS:
            raise PolicyError(
                f"unsupported ingestion adapter: {adapter!r}",
                context={"supported": sorted(SUPPORTED_INGESTION_ADAPTERS)},
            )
        paths = [str(path) for path in data.get("paths", [])]
        hermes_db_path = data.get("hermes_db_path")
        if hermes_db_path is not None:
            hermes_db_path = str(hermes_db_path)
        max_sessions = int(data.get("max_sessions", 20))
        if max_sessions <= 0:
            raise PolicyError(f"ingestion.max_sessions must be positive, got {max_sessions}")
        for field_name, value in (("adapter", adapter), ("hermes_db_path", hermes_db_path)):
            if value is not None:
                validate_field_size(value, label=f"ingestion.{field_name}")
        for index, path in enumerate(paths):
            validate_field_size(path, label=f"ingestion.paths[{index}]")
        return cls(
            enabled=bool(data.get("enabled", False)),
            adapter=adapter,
            paths=paths,
            hermes_db_path=hermes_db_path,
            latest=bool(data.get("latest", False)),
            max_sessions=max_sessions,
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
        if not 0 <= min_score <= 100:
            raise PolicyError(f"evaluation.min_score must be in 0..100, got {min_score}")
        evaluator = str(data.get("evaluator") or "rubric")
        if evaluator not in SUPPORTED_EVALUATORS:
            raise PolicyError(
                f"unsupported evaluation evaluator: {evaluator!r}",
                context={"supported": sorted(SUPPORTED_EVALUATORS)},
            )
        limit = data.get("limit")
        if limit is not None and int(limit) <= 0:
            raise PolicyError(f"evaluation.limit must be positive, got {limit}")
        validate_field_size(evaluator, label="evaluation.evaluator")
        return cls(
            evaluator=evaluator,
            min_score=min_score,
            only_unevaluated=bool(data.get("only_unevaluated", True)),
            distill_failures=bool(data.get("distill_failures", True)),
            limit=limit,
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
    auto_update: bool = False
    kind: str = "sft"
    out: str = "data/sft.jsonl"
    min_score: int = 70
    splits: str = "train=0.8,validation=0.1,test=0.1"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "DatasetPolicy":
        data = dict(data or {})
        enabled = bool(data.get("enabled", False))
        kind = str(data.get("kind") or "sft")
        if kind not in SUPPORTED_DATASET_KINDS:
            raise PolicyError(
                f"unsupported dataset kind: {kind!r}",
                context={"supported": sorted(SUPPORTED_DATASET_KINDS)},
            )
        out = str(data.get("out") or "data/sft.jsonl")
        min_score = int(data.get("min_score", 70))
        if not 0 <= min_score <= 100:
            raise PolicyError(f"dataset.min_score must be in 0..100, got {min_score}")
        splits = str(data.get("splits") or "train=0.8,validation=0.1,test=0.1")
        validate_field_size(out, label="dataset.out")
        validate_field_size(splits, label="dataset.splits")
        return cls(
            enabled=enabled,
            auto_update=bool(data.get("auto_update", enabled)),
            kind=kind,
            out=out,
            min_score=min_score,
            splits=splits,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "auto_update": self.auto_update,
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
        if max_cost is not None:
            max_cost = float(max_cost)
            if max_cost <= 0:
                raise PolicyError(f"training.max_cost_usd must be positive, got {max_cost}")
        target = str(data.get("target") or "axolotl")
        if target not in SUPPORTED_TRAINING_TARGETS:
            raise PolicyError(
                f"unsupported training target: {target!r}",
                context={"supported": sorted(SUPPORTED_TRAINING_TARGETS)},
            )
        base_model = str(data.get("base_model") or "")
        validate_field_size(base_model, label="training.base_model")
        return cls(
            auto_plan=bool(data.get("auto_plan", False)),
            auto_run=bool(data.get("auto_run", False)),
            require_approval=bool(data.get("require_approval", True)),
            target=target,
            base_model=base_model,
            max_cost_usd=max_cost,
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
        data = dict(data or {})
        version = str(data.get("version") or POLICY_VERSION)
        if version != POLICY_VERSION:
            raise PolicyError(f"unsupported policy version: {version!r} (expected {POLICY_VERSION})")
        mode = str(data.get("mode") or "autonomous_review_first")
        if mode not in SUPPORTED_MODES:
            raise PolicyError(
                f"unsupported mode: {mode!r}",
                context={"supported": sorted(SUPPORTED_MODES)},
            )
        return cls(
            version=version,
            mode=mode,
            ingestion=IngestionPolicy.from_dict(data.get("ingestion")),
            evaluation=EvaluationPolicy.from_dict(data.get("evaluation")),
            dataset=DatasetPolicy.from_dict(data.get("dataset")),
            training=TrainingPolicy.from_dict(data.get("training")),
        )

    @classmethod
    def load(cls, path: str | Path) -> "SkillLoopPolicy":
        try:
            raw = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            from skillloop.errors import ConfigError

            raise ConfigError(f"failed to read policy file: {path}") from exc
        return cls.from_dict(json.loads(raw))

    def save(self, path: str | Path) -> Path:
        from skillloop.fs_safety import atomic_write_json

        out = Path(path).resolve()
        atomic_write_json(out, self.to_dict())
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
