#!/usr/bin/env python3
"""Produce a secret-safe Openship context and repository preflight report.

The helper intentionally relies on public CLI output. It never reads
~/.openship/config.json and never prints bearer credentials or secret values.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import _openship  # noqa: E402
import _preflight_core  # noqa: E402
import _repository  # noqa: E402
from _preflight_core import build_report  # noqa: E402
from _repository import git_report, read_project_link  # noqa: E402
from _runtime import (  # noqa: E402
    CommandResult,
    DEFAULT_TIMEOUT_SECONDS,
    SCHEMA_VERSION,
    issue,
    parse_json_output,
    redact,
    run_command,
    utc_now,
)


def parser() -> argparse.ArgumentParser:
    arg_parser = argparse.ArgumentParser(
        description="Print a secret-safe Openship CLI/context/repository preflight report as JSON."
    )
    arg_parser.add_argument("--cwd", default=".", help="Working directory to inspect (default: current directory).")
    arg_parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Per-command timeout in seconds (default: {DEFAULT_TIMEOUT_SECONDS:g}).",
    )
    arg_parser.add_argument("--strict", action="store_true", help="Exit 2 when the report contains a blocking safety error.")
    arg_parser.add_argument(
        "--require-api",
        action="store_true",
        help="Exit 3 when the active Openship API is not confirmed reachable.",
    )
    arg_parser.add_argument("--compact", action="store_true", help="Emit compact JSON instead of indented JSON.")
    return arg_parser


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    cwd = Path(args.cwd).expanduser()
    if not cwd.exists() or not cwd.is_dir():
        payload = {
            "schemaVersion": SCHEMA_VERSION,
            "generatedAt": utc_now(),
            "ready": False,
            "errors": [issue("CWD_INVALID", f"Working directory does not exist: {cwd}", blocking=True)],
        }
        print(json.dumps(payload, indent=None if args.compact else 2, sort_keys=True))
        return 2

    try:
        report = build_report(cwd.resolve(), max(0.1, args.timeout))
    except Exception as exc:  # Defensive boundary for an operator helper.
        report = {
            "schemaVersion": SCHEMA_VERSION,
            "generatedAt": utc_now(),
            "ready": False,
            "errors": [issue("PREFLIGHT_INTERNAL_ERROR", redact(str(exc)), blocking=True)],
        }
        print(json.dumps(report, indent=None if args.compact else 2, sort_keys=True))
        return 1

    print(json.dumps(report, indent=None if args.compact else 2, sort_keys=True))
    if args.strict and not report.get("ready", False):
        return 2
    if args.require_api and report.get("instance", {}).get("reachable") is not True:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
