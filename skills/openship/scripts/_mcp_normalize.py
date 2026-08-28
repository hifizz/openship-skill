"""Normalize and filter Openship MCP tool and prompt descriptors."""

from __future__ import annotations

import json
from typing import Any

from _mcp_client import CatalogError


def normalize_tools(response: dict[str, Any]) -> list[dict[str, Any]]:
    result = response.get("result", {})
    raw_tools = result.get("tools") if isinstance(result, dict) else None
    if not isinstance(raw_tools, list):
        raise CatalogError("tools/list result does not contain a tools array.")

    tools: list[dict[str, Any]] = []
    for raw in raw_tools:
        if not isinstance(raw, dict) or not isinstance(raw.get("name"), str):
            continue
        annotations = raw.get("annotations") if isinstance(raw.get("annotations"), dict) else {}
        schema = raw.get("inputSchema") if isinstance(raw.get("inputSchema"), dict) else {}
        tools.append(
            {
                "name": raw["name"],
                "description": raw.get("description") if isinstance(raw.get("description"), str) else "",
                "readOnly": bool(annotations.get("readOnlyHint")),
                "destructive": bool(annotations.get("destructiveHint")),
                "inputSchema": schema,
            }
        )
    tools.sort(key=lambda item: item["name"])
    return tools


def normalize_prompts(response: dict[str, Any]) -> list[dict[str, Any]]:
    result = response.get("result", {})
    raw_prompts = result.get("prompts") if isinstance(result, dict) else None
    if not isinstance(raw_prompts, list):
        raise CatalogError("prompts/list result does not contain a prompts array.")

    prompts: list[dict[str, Any]] = []
    for raw in raw_prompts:
        if not isinstance(raw, dict) or not isinstance(raw.get("name"), str):
            continue
        arguments: list[dict[str, Any]] = []
        if isinstance(raw.get("arguments"), list):
            for argument in raw["arguments"]:
                if not isinstance(argument, dict) or not isinstance(argument.get("name"), str):
                    continue
                arguments.append(
                    {
                        "name": argument["name"],
                        "description": argument.get("description")
                        if isinstance(argument.get("description"), str)
                        else "",
                        "required": bool(argument.get("required")),
                    }
                )
        prompts.append(
            {
                "name": raw["name"],
                "title": raw.get("title") if isinstance(raw.get("title"), str) else "",
                "description": raw.get("description") if isinstance(raw.get("description"), str) else "",
                "arguments": arguments,
            }
        )
    prompts.sort(key=lambda item: item["name"])
    return prompts


def matches_search(item: dict[str, Any], term: str | None) -> bool:
    if not term:
        return True
    needle = term.casefold()
    haystack = json.dumps(item, ensure_ascii=False, sort_keys=True).casefold()
    return needle in haystack


def filter_tools(
    tools: list[dict[str, Any]],
    *,
    search: str | None,
    read_mode: str | None,
    risk_mode: str | None,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for tool in tools:
        if not matches_search(tool, search):
            continue
        if read_mode == "read-only" and not tool["readOnly"]:
            continue
        if read_mode == "mutating" and tool["readOnly"]:
            continue
        if risk_mode == "destructive" and not tool["destructive"]:
            continue
        if risk_mode == "safe-only" and tool["destructive"]:
            continue
        output.append(tool)
    return output


def filter_prompts(prompts: list[dict[str, Any]], *, search: str | None) -> list[dict[str, Any]]:
    return [prompt for prompt in prompts if matches_search(prompt, search)]
