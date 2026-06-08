from __future__ import annotations

from pathlib import Path

from skillloop.review.queue import write_approved_files
from skillloop.store import SkillLoopStore


def export_approved(store: SkillLoopStore, out_dir: str | Path | None = None) -> list[Path]:
    """Cleanly export approved proposals to files inside the project root."""
    return write_approved_files(store, out_dir=out_dir)
