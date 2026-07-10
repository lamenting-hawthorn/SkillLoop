"""Read-only installation and project diagnostics."""

from __future__ import annotations

import os
import sqlite3
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from skillloop import __version__
from skillloop.fs_safety import resolve_under_root
from skillloop.policy import POLICY_VERSION, SkillLoopPolicy

DiagnosticStatus = Literal["pass", "warn", "fail"]


@dataclass(frozen=True)
class DiagnosticCheck:
    name: str
    status: DiagnosticStatus
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _check_project_root(root: Path) -> DiagnosticCheck:
    if not root.exists():
        return DiagnosticCheck("project_root", "fail", f"does not exist: {root}")
    if not root.is_dir():
        return DiagnosticCheck("project_root", "fail", f"is not a directory: {root}")
    if not os.access(root, os.R_OK | os.W_OK | os.X_OK):
        return DiagnosticCheck("project_root", "fail", f"is not readable and writable: {root}")
    return DiagnosticCheck("project_root", "pass", str(root))


def _check_database(state_dir: Path) -> DiagnosticCheck:
    database = state_dir / "skillloop.db"
    if not database.exists():
        return DiagnosticCheck(
            "database", "warn", "not initialized; run `skillloop --path <project> init`"
        )
    try:
        with sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True) as connection:
            result = connection.execute("PRAGMA quick_check").fetchone()
    except sqlite3.Error as exc:
        return DiagnosticCheck("database", "fail", f"cannot read {database}: {exc}")
    if result != ("ok",):
        return DiagnosticCheck("database", "fail", f"integrity check failed: {result!r}")
    return DiagnosticCheck("database", "pass", str(database))


def _check_policy(root: Path, state_dir: Path) -> list[DiagnosticCheck]:
    policy_path = state_dir / "policy.json"
    if not policy_path.exists():
        return [
            DiagnosticCheck("policy", "warn", "not configured; manual commands remain available")
        ]
    try:
        policy = SkillLoopPolicy.load(policy_path)
    except (OSError, ValueError, TypeError) as exc:
        return [DiagnosticCheck("policy", "fail", f"cannot load {policy_path}: {exc}")]
    checks = [
        DiagnosticCheck(
            "policy",
            "pass" if policy.version == POLICY_VERSION else "warn",
            f"version {policy.version}",
        )
    ]
    try:
        resolve_under_root(root, policy.dataset.out, label="dataset output")
    except ValueError as exc:
        checks.append(DiagnosticCheck("dataset_output", "fail", str(exc)))
    else:
        checks.append(DiagnosticCheck("dataset_output", "pass", policy.dataset.out))
    if policy.ingestion.enabled and policy.ingestion.adapter == "hermes-db":
        configured = policy.ingestion.hermes_db_path
        path = Path(configured).expanduser() if configured else None
        checks.append(
            DiagnosticCheck(
                "hermes_database",
                "pass" if path and path.is_file() else "fail",
                str(path.resolve())
                if path and path.is_file()
                else f"not found: {configured or '<not configured>'}",
            )
        )
    return checks


def run_diagnostics(root: str | Path) -> list[DiagnosticCheck]:
    project_root = Path(root).expanduser().resolve()
    checks = [
        DiagnosticCheck("skillloop", "pass", f"version {__version__}"),
        DiagnosticCheck("python", "pass", sys.version.split()[0]),
        _check_project_root(project_root),
    ]
    if checks[-1].status == "fail":
        return checks
    state_dir = project_root / ".skillloop"
    checks.append(_check_database(state_dir))
    checks.extend(_check_policy(project_root, state_dir))
    return checks
