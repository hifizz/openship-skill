"""Safe parsers for Openship CLI JSON surfaces."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from _runtime import CommandResult, parse_json_output, run_command


def openship_json(
    binary: str,
    args: Sequence[str],
    *,
    cwd: Path,
    timeout: float,
) -> tuple[CommandResult, Any | None]:
    result = run_command([binary, "--json", *args], cwd=cwd, timeout=timeout)
    payload = parse_json_output(result.stdout)
    if payload is not None:
        return result, payload
    fallback = run_command([binary, *args], cwd=cwd, timeout=timeout)
    return fallback, parse_json_output(fallback.stdout)


def safe_contexts(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    output: list[dict[str, Any]] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        output.append(
            {
                "current": row.get("current") == "*" or row.get("current") is True,
                "name": row.get("name") if isinstance(row.get("name"), str) else None,
                "apiUrl": row.get("apiUrl") if isinstance(row.get("apiUrl"), str) else None,
                "dashboardUrl": row.get("dashboardUrl")
                if isinstance(row.get("dashboardUrl"), str)
                else None,
                "authenticated": row.get("auth") == "token" or row.get("hasToken") is True,
            }
        )
    return output


def pick_env(status_payload: Any, health_payload: Any) -> dict[str, Any]:
    if isinstance(status_payload, dict) and isinstance(status_payload.get("env"), dict):
        return status_payload["env"]
    if isinstance(health_payload, dict):
        if isinstance(health_payload.get("data"), dict):
            return health_payload["data"]
        return health_payload
    return {}


def capability_report(env_payload: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "selfHosted",
        "deployMode",
        "authMode",
        "teamMode",
        "hasLocalHost",
        "hasLocalDocker",
        "cloudMode",
    )
    return {key: env_payload.get(key) for key in keys if key in env_payload}
