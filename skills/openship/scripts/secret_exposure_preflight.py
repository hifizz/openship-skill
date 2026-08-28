#!/usr/bin/env python3
"""Fail-closed Secret Exposure Gate for Openship operations.

The report contains file paths, environment key names, sink classifications,
and pattern identifiers only. It never emits secret values or matching source
snippets. Real secrets must never be used as canaries.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from _secret_exposure import OPERATION_SINKS, build_exposure_plan, safe_diagnostic  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parser() -> argparse.ArgumentParser:
    arg_parser = argparse.ArgumentParser(
        description="Classify secret sources and output sinks before an Openship build or sensitive operation."
    )
    arg_parser.add_argument("--cwd", default=".", help="Repository or folder to inspect (default: current directory).")
    arg_parser.add_argument("--operation", choices=tuple(OPERATION_SINKS), required=True)
    arg_parser.add_argument(
        "--remote-env-state",
        choices=("unknown", "none", "present"),
        default="unknown",
        help="Secret-safe result of inspecting the selected Openship environment (default: unknown).",
    )
    arg_parser.add_argument(
        "--sensitive-key",
        action="append",
        default=[],
        help="Declare a sensitive key name without supplying its value. Repeat as needed.",
    )
    arg_parser.add_argument(
        "--evidence-file",
        type=Path,
        help="JSON evidence that classifies output sinks using schema/live-doc/canary verification.",
    )
    arg_parser.add_argument("--output", type=Path, help="Also save the generated plan to this path with mode 0600.")
    arg_parser.add_argument("--compact", action="store_true", help="Emit compact JSON.")
    arg_parser.add_argument(
        "--fail-closed",
        action="store_true",
        help="Exit 4 unless the decision is allow or allow-with-redaction.",
    )
    return arg_parser


def write_secure(path: Path, rendered: str) -> None:
    destination = path.expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(rendered + ("" if rendered.endswith("\n") else "\n"), encoding="utf-8")
    try:
        destination.chmod(0o600)
    except OSError:
        pass


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = Path(args.cwd).expanduser()
    if not root.exists() or not root.is_dir():
        error = {
            "schemaVersion": "0.2",
            "generatedAt": utc_now(),
            "decision": "blocked",
            "error": {"code": "CWD_INVALID", "message": f"Working directory does not exist: {root}"},
        }
        print(json.dumps(error, indent=None if args.compact else 2, sort_keys=True))
        return 2

    try:
        plan = build_exposure_plan(
            root=root.resolve(),
            operation=args.operation,
            remote_env_state=args.remote_env_state,
            evidence_file=args.evidence_file,
            sensitive_keys=args.sensitive_key,
        )
        plan["generatedAt"] = utc_now()
    except (OSError, ValueError) as exc:
        error = {
            "schemaVersion": "0.2",
            "generatedAt": utc_now(),
            "decision": "blocked",
            "error": {"code": "SECRET_EXPOSURE_PREFLIGHT_FAILED", "message": safe_diagnostic(str(exc))},
        }
        print(json.dumps(error, indent=None if args.compact else 2, sort_keys=True))
        return 2

    rendered = json.dumps(plan, indent=None if args.compact else 2, sort_keys=True, ensure_ascii=False)
    if args.output:
        write_secure(args.output, rendered)
    print(rendered)

    if args.fail_closed and plan["decision"] not in {"allow", "allow-with-redaction"}:
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
