from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from skillloop.conditions import LoopCondition


@dataclass
class SetupRequest:
    connect: str
    db_path: Path
    max_sessions: int
    min_score: int
    auto_export: bool
    dataset_out: str
    start: bool


@dataclass
class IngestionRequest:
    adapter: str
    input: Path | None
    db_path: Path
    session_id: str | None
    latest: bool


@dataclass
class ExportRequest:
    format: str
    out: Path
    manifest_out: Path | None
    splits: str | None
    trace_id: str | None
    min_score: int | None


@dataclass
class BenchmarkRequest:
    baseline: str
    candidates: list[str]
    trace_id: str | None
    out: str | None


@dataclass
class LoopRunRequest:
    evaluator: str
    min_score: int
    condition: LoopCondition
    require_tag: tuple[str, ...]
    forbid_tag: tuple[str, ...]
    max_iterations: int | None
    reevaluate_all: bool
    distill_failures: bool
    limit: int | None


@dataclass
class LoopScheduleRequest:
    interval: str
    evaluator: str
    min_score: int
    condition: LoopCondition
    require_tag: tuple[str, ...]
    forbid_tag: tuple[str, ...]
    max_iterations: int | None
    reevaluate_all: bool
    distill_failures: bool
    limit: int | None


@dataclass
class ServiceInstallRequest:
    kind: str | None
    interval_seconds: int
    label: str | None
    launch_agents_dir: str | None
