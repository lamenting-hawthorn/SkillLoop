from __future__ import annotations

import argparse
import json

from skillloop.diagnostics import run_diagnostics


def cmd_doctor(args: argparse.Namespace) -> int:
    checks = run_diagnostics(args.path)
    if args.json:
        print(
            json.dumps(
                {"checks": [check.to_dict() for check in checks]}, indent=2, ensure_ascii=False
            )
        )
    else:
        for check in checks:
            print(f"{check.status.upper():4}  {check.name}: {check.message}")
    return 1 if any(check.status == "fail" for check in checks) else 0


__all__ = ["cmd_doctor"]
