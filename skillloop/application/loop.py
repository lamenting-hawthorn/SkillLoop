from __future__ import annotations

from dataclasses import dataclass

from skillloop.loop import LoopSchedule, load_schedule, run_outer_loop, save_schedule, tick

from .requests import LoopRunRequest, LoopScheduleRequest


@dataclass
class LoopTickResult:
    ran: bool
    summary: object | None
    schedule: object


class LoopService:
    def run(self, store, req: LoopRunRequest):
        return run_outer_loop(
            store,
            evaluator=req.evaluator,
            min_score=req.min_score,
            condition=req.condition,
            only_unevaluated=not req.reevaluate_all,
            distill_failures=req.distill_failures,
            limit=req.limit,
        )

    def schedule(self, store, req: LoopScheduleRequest) -> str:
        schedule = LoopSchedule(
            interval=req.interval,
            evaluator=req.evaluator,
            min_score=req.condition.score_gte,
            condition=req.condition,
            only_unevaluated=not req.reevaluate_all,
            distill_failures=req.distill_failures,
            limit=req.limit,
        )
        return str(save_schedule(store, schedule))

    def status(self, store) -> LoopSchedule:
        return load_schedule(store)

    def tick(self, store, force: bool) -> LoopTickResult:
        ran, summary, schedule = tick(store, force=force)
        return LoopTickResult(ran=ran, summary=summary, schedule=schedule)


__all__ = ["LoopService", "LoopTickResult"]
