from __future__ import annotations

from skillloop.benchmark import replay_benchmark, write_benchmark_report
from skillloop.eval.registry import default_evaluator_registry
from skillloop.schema import AgentTrace
from skillloop.store import SkillLoopStore

from .requests import BenchmarkRequest


class BenchmarkService:
    def __init__(self, store: SkillLoopStore) -> None:
        self._store = store

    def run(self, traces: list[AgentTrace], req: BenchmarkRequest) -> tuple[object, str | None]:
        report = replay_benchmark(
            traces, default_evaluator_registry(), baseline=req.baseline, candidates=req.candidates
        )
        out_path = None
        if req.out:
            out_path = write_benchmark_report(req.out, report)
        return report, out_path


__all__ = ["BenchmarkService"]
