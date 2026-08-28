"""JSON-RPC transport for Openship's /api/mcp endpoint."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from _runtime import CommandResult, parse_json_output, redact, run_command


class CatalogError(RuntimeError):
    """A sanitized catalog retrieval or normalization failure."""


def rpc_request(
    binary: str,
    method: str,
    *,
    request_id: int,
    params: dict[str, Any] | None,
    timeout: float,
) -> dict[str, Any]:
    envelope: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        envelope["params"] = params
    body = json.dumps(envelope, separators=(",", ":"), ensure_ascii=False)

    result = run_command(
        [binary, "--json", "api", "/mcp", "--method", "POST", "--data", body],
        cwd=Path.cwd(),
        timeout=timeout,
    )
    payload = parse_json_output(result.stdout)
    if payload is None:
        detail = redact(result.stderr) or "no JSON response"
        if result.timed_out:
            detail = f"request timed out; {detail}"
        raise CatalogError(f"MCP {method} failed: {detail}")
    if not isinstance(payload, dict):
        raise CatalogError(f"MCP {method} returned a non-object JSON-RPC response.")

    error = payload.get("error")
    if isinstance(error, dict):
        code = error.get("code")
        message = redact(str(error.get("message") or "unknown JSON-RPC error"))
        raise CatalogError(f"MCP {method} error {code}: {message}")
    if result.returncode != 0 and "result" not in payload:
        detail = redact(result.stderr) or f"openship exited {result.returncode}"
        raise CatalogError(f"MCP {method} failed: {detail}")
    if not isinstance(payload.get("result"), dict):
        raise CatalogError(f"MCP {method} response is missing an object result.")
    return payload


__all__ = ["CatalogError", "CommandResult", "rpc_request", "run_command"]
