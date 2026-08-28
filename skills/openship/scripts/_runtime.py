"""Shared, secret-safe subprocess and JSON helpers for the Openship skill."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from _secret_exposure import safe_diagnostic

SCHEMA_VERSION = "0.2"
DEFAULT_TIMEOUT_SECONDS = 12.0
MAX_DIAGNOSTIC_CHARS = 600


@dataclass(frozen=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    not_found: bool = False


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def redact(text: str) -> str:
    """Redact credential-like values and bound diagnostic size."""

    return safe_diagnostic(text or "", max_chars=MAX_DIAGNOSTIC_CHARS)


def run_command(
    args: Sequence[str],
    *,
    cwd: Path,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> CommandResult:
    """Run a command without a shell and return captured text output.

    Callers must not place secret values in ``args``. Capturing output does not
    prove the producing system avoided persisting plaintext upstream.
    """

    command = tuple(str(part) for part in args)
    env = os.environ.copy()
    env.setdefault("NO_COLOR", "1")
    env.setdefault("OPENSHIP_JSON", "1")
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return CommandResult(
            args=command,
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )
    except FileNotFoundError as exc:
        return CommandResult(command, 127, "", str(exc), not_found=True)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return CommandResult(command, 124, stdout, stderr, timed_out=True)


def parse_json_output(text: str) -> Any | None:
    """Parse JSON despite a small accidental text prefix or suffix."""

    raw = (text or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    for line in reversed(raw.splitlines()):
        candidate = line.strip()
        if not candidate or candidate[0] not in "[{":
            continue
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    decoder = json.JSONDecoder()
    for index, char in enumerate(raw):
        if char not in "[{":
            continue
        try:
            value, end = decoder.raw_decode(raw[index:])
        except json.JSONDecodeError:
            continue
        if not raw[index + end :].strip():
            return value
    return None


def issue(code: str, message: str, *, blocking: bool) -> dict[str, Any]:
    return {"code": code, "message": message, "blocking": blocking}


def command_text(result: CommandResult) -> str | None:
    value = (result.stdout or "").strip()
    return value or None


def extract_version(raw: str | None) -> str | None:
    if not raw:
        return None
    match = re.search(r"(?<!\d)v?(\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)", raw)
    return match.group(1) if match else None
