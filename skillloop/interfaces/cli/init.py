from __future__ import annotations

import argparse

from skillloop.interfaces.cli._shared import _store


def cmd_init(args: argparse.Namespace) -> int:
    store = _store(args)
    store.init()
    print(f"Initialized SkillLoop at {store.state_dir}")
    print("Next: ingest a trace, then run `skillloop --path <project> eval latest`")
    return 0


__all__ = ["cmd_init"]
