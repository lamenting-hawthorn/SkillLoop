from __future__ import annotations

from skillloop.interfaces.cli.controller import cmd_controller_history, cmd_controller_run, cmd_controller_show
from skillloop.interfaces.cli.dataset import cmd_benchmark, cmd_training_config
from skillloop.interfaces.cli.distill import cmd_distill
from skillloop.interfaces.cli.doctor import cmd_doctor
from skillloop.interfaces.cli.evaluate import cmd_eval
from skillloop.interfaces.cli.export import cmd_export
from skillloop.interfaces.cli.init import cmd_init
from skillloop.interfaces.cli.ingest import cmd_ingest, cmd_traces_list, cmd_traces_show
from skillloop.interfaces.cli.loop import cmd_loop_run, cmd_loop_schedule, cmd_loop_status, cmd_loop_tick
from skillloop.interfaces.cli.main import build_parser, main
from skillloop.interfaces.cli.review import cmd_apply, cmd_review_approve, cmd_review_list, cmd_review_reject
from skillloop.interfaces.cli.service import cmd_service_install, cmd_service_status, cmd_service_uninstall
from skillloop.interfaces.cli.setup import cmd_setup
from skillloop.interfaces.cli.status import cmd_status

__all__ = [
    "build_parser",
    "main",
    "cmd_init",
    "cmd_doctor",
    "cmd_setup",
    "cmd_status",
    "cmd_ingest",
    "cmd_traces_list",
    "cmd_traces_show",
    "cmd_eval",
    "cmd_distill",
    "cmd_review_list",
    "cmd_review_approve",
    "cmd_review_reject",
    "cmd_apply",
    "cmd_export",
    "cmd_benchmark",
    "cmd_training_config",
    "cmd_loop_run",
    "cmd_loop_schedule",
    "cmd_loop_status",
    "cmd_loop_tick",
    "cmd_controller_run",
    "cmd_controller_history",
    "cmd_controller_show",
    "cmd_service_install",
    "cmd_service_status",
    "cmd_service_uninstall",
]
