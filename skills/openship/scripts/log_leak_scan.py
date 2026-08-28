#!/usr/bin/env python3
"""Sanitize a bounded CLI/API/log payload before it enters Agent context.

This is a second line of defense. It cannot undo a secret already persisted by
Openship, Docker, CI, or another logging backend. Run the Secret Exposure Gate
before the producing operation.
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

from _secret_exposure import sanitize_text  # noqa: E402

DEFAULT_MAX_BYTES = 5_000_000


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parser() -> argparse.ArgumentParser:
    arg_parser = argparse.ArgumentParser(
        description="Redact common credentials and canaries from bounded text before showing it to an Agent."
    )
    arg_parser.add_argument("path", nargs="?", type=Path, help="Input file. Omit or use '-' to read stdin.")
    arg_parser.add_argument("--canary", action="append", default=[], help="Disposable fake-secret marker to detect/redact.")
    arg_parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    arg_parser.add_argument("--report", type=Path, help="Write a metadata-only JSON detection report with mode 0600.")
    arg_parser.add_argument("--quiet", action="store_true", help="Do not print sanitized text; emit only the optional report.")
    arg_parser.add_argument("--fail-on-detection", action="store_true", help="Exit 4 when any credential pattern is detected.")
    return arg_parser


def read_bounded(path: Path | None, max_bytes: int) -> bytes:
    if max_bytes < 1:
        raise ValueError("max-bytes must be positive")
    if path is None or str(path) == "-":
        data = sys.stdin.buffer.read(max_bytes + 1)
    else:
        with path.expanduser().open("rb") as handle:
            data = handle.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("Input exceeds max-bytes; select a smaller log range instead of exposing an unbounded payload")
    return data


def write_report(path: Path, report: dict[str, object]) -> None:
    destination = path.expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        destination.chmod(0o600)
    except OSError:
        pass


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        raw = read_bounded(args.path, args.max_bytes)
    except (OSError, ValueError) as exc:
        print(f"log_leak_scan: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    text = raw.decode("utf-8", errors="replace")
    sanitized, detections = sanitize_text(text, canaries=args.canary)
    report: dict[str, object] = {
        "schemaVersion": "0.2",
        "generatedAt": utc_now(),
        "inputBytes": len(raw),
        "detected": bool(detections),
        "detections": detections,
        "rawValuesRecorded": False,
        "warning": "Redaction protects this output only; it does not remove plaintext already persisted upstream.",
    }

    if args.report:
        write_report(args.report, report)
    if not args.quiet:
        sys.stdout.write(sanitized)
        if sanitized and not sanitized.endswith("\n"):
            sys.stdout.write("\n")
    if args.fail_on_detection and detections:
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
