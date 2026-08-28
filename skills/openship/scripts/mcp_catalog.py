#!/usr/bin/env python3
"""Read and normalize the live Openship MCP tool/prompt catalog.

The script calls /api/mcp through `openship api`, allowing the CLI to handle the
active context and bearer token. It never reads the credential file itself.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Sequence

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import _mcp_client  # noqa: E402
from _mcp_client import CatalogError, CommandResult, rpc_request  # noqa: E402
from _mcp_normalize import (  # noqa: E402
    filter_prompts,
    filter_tools,
    normalize_prompts,
    normalize_tools,
)
from _runtime import DEFAULT_TIMEOUT_SECONDS, SCHEMA_VERSION, redact, utc_now  # noqa: E402


def build_catalog(args: argparse.Namespace) -> dict[str, Any]:
    binary = shutil.which(args.openship)
    if not binary:
        raise CatalogError(f"Openship CLI not found on PATH: {args.openship}")

    tools: list[dict[str, Any]] = []
    prompts: list[dict[str, Any]] = []
    raw_tool_count = 0
    raw_prompt_count = 0
    request_id = 1

    if args.kind in {"tools", "all"}:
        response = rpc_request(binary, "tools/list", request_id=request_id, params=None, timeout=args.timeout)
        request_id += 1
        all_tools = normalize_tools(response)
        raw_tool_count = len(all_tools)
        tools = filter_tools(
            all_tools,
            search=args.search,
            read_mode=args.read_mode,
            risk_mode=args.risk_mode,
        )

    if args.kind in {"prompts", "all"}:
        response = rpc_request(binary, "prompts/list", request_id=request_id, params=None, timeout=args.timeout)
        all_prompts = normalize_prompts(response)
        raw_prompt_count = len(all_prompts)
        prompts = filter_prompts(all_prompts, search=args.search)

    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": utc_now(),
        "source": "openship api /mcp",
        "kind": args.kind,
        "filters": {
            "search": args.search,
            "readMode": args.read_mode,
            "riskMode": args.risk_mode,
        },
        "counts": {
            "rawTools": raw_tool_count,
            "returnedTools": len(tools),
            "readOnlyTools": sum(1 for tool in tools if tool["readOnly"]),
            "mutatingTools": sum(1 for tool in tools if not tool["readOnly"]),
            "destructiveTools": sum(1 for tool in tools if tool["destructive"]),
            "rawPrompts": raw_prompt_count,
            "returnedPrompts": len(prompts),
        },
        "tools": tools,
        "prompts": prompts,
    }


def write_output(path: Path, content: str) -> None:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content + ("" if content.endswith("\n") else "\n"), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def parser() -> argparse.ArgumentParser:
    arg_parser = argparse.ArgumentParser(
        description="Read Openship's permission-filtered MCP tools/prompts through the local CLI."
    )
    arg_parser.add_argument("--kind", choices=("tools", "prompts", "all"), default="tools")
    arg_parser.add_argument("--search", help="Case-insensitive search across names, descriptions, and schemas.")
    read_group = arg_parser.add_mutually_exclusive_group()
    read_group.add_argument("--read-only", dest="read_mode", action="store_const", const="read-only")
    read_group.add_argument("--mutating", dest="read_mode", action="store_const", const="mutating")
    risk_group = arg_parser.add_mutually_exclusive_group()
    risk_group.add_argument("--destructive", dest="risk_mode", action="store_const", const="destructive")
    risk_group.add_argument("--safe-only", dest="risk_mode", action="store_const", const="safe-only")
    arg_parser.add_argument("--openship", default="openship", help="CLI executable name to resolve on PATH.")
    arg_parser.add_argument("--timeout", type=float, default=20.0, help="Per-request timeout in seconds.")
    arg_parser.add_argument("--output", type=Path, help="Also save the normalized JSON catalog to this path.")
    arg_parser.add_argument("--fail-on-empty", action="store_true", help="Exit 3 when filters return no items.")
    arg_parser.add_argument("--compact", action="store_true", help="Emit compact JSON instead of indented JSON.")
    return arg_parser


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    args.timeout = max(0.1, args.timeout)
    try:
        catalog = build_catalog(args)
        rendered = json.dumps(catalog, indent=None if args.compact else 2, sort_keys=True, ensure_ascii=False)
        if args.output:
            write_output(args.output, rendered)
        print(rendered)
        if args.fail_on_empty:
            returned = catalog["counts"]["returnedTools"] + catalog["counts"]["returnedPrompts"]
            if returned == 0:
                return 3
        return 0
    except CatalogError as exc:
        error = {
            "schemaVersion": SCHEMA_VERSION,
            "generatedAt": utc_now(),
            "source": "openship api /mcp",
            "error": {"code": "MCP_CATALOG_FAILED", "message": redact(str(exc))},
        }
        print(json.dumps(error, indent=None if args.compact else 2, sort_keys=True, ensure_ascii=False))
        return 2
    except Exception as exc:  # Defensive boundary for a command-line helper.
        error = {
            "schemaVersion": SCHEMA_VERSION,
            "generatedAt": utc_now(),
            "source": "openship api /mcp",
            "error": {"code": "MCP_CATALOG_INTERNAL_ERROR", "message": redact(str(exc))},
        }
        print(json.dumps(error, indent=None if args.compact else 2, sort_keys=True, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
