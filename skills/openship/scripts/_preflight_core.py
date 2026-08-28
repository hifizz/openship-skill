"""Build the normalized Openship preflight report."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from _openship import capability_report, openship_json, pick_env, safe_contexts
from _repository import git_report, read_project_link
from _runtime import command_text, extract_version, issue, redact, run_command, utc_now


def _initial_instance() -> dict[str, Any]:
    return {
        "activeContext": None,
        "apiUrl": None,
        "dashboardUrl": None,
        "authenticated": None,
        "reachable": None,
        "mode": None,
        "health": None,
        "deployMode": None,
        "authMode": None,
        "teamMode": None,
        "hostDomain": None,
        "machineName": None,
    }


def _inspect_cli(
    binary: str,
    *,
    cwd: Path,
    timeout: float,
    warnings: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    cli: dict[str, Any] = {
        "installed": True,
        "path": binary,
        "version": None,
        "versionRaw": None,
    }
    instance = _initial_instance()

    version_result = run_command([binary, "--version"], cwd=cwd, timeout=timeout)
    version_raw = command_text(version_result) or redact(version_result.stderr)
    cli["versionRaw"] = version_raw
    cli["version"] = extract_version(version_raw)
    if version_result.returncode != 0:
        warnings.append(
            issue(
                "OPENSHIP_VERSION_FAILED",
                f"Could not read the Openship CLI version: {redact(version_result.stderr) or 'unknown error'}",
                blocking=False,
            )
        )
    elif cli["version"] is None:
        warnings.append(issue("OPENSHIP_VERSION_UNPARSED", "The CLI version output could not be normalized.", blocking=False))

    context_result, context_payload = openship_json(binary, ["context", "list"], cwd=cwd, timeout=timeout)
    contexts = safe_contexts(context_payload)
    active_row = next((row for row in contexts if row["current"]), None)
    if active_row:
        instance.update(
            {
                "activeContext": active_row["name"],
                "apiUrl": active_row["apiUrl"],
                "dashboardUrl": active_row["dashboardUrl"],
                "authenticated": active_row["authenticated"],
            }
        )
    elif context_result.returncode != 0:
        warnings.append(
            issue(
                "CONTEXT_LIST_FAILED",
                f"Could not list safe context metadata: {redact(context_result.stderr) or 'unknown error'}",
                blocking=False,
            )
        )

    status_result, status_payload = openship_json(binary, ["status"], cwd=cwd, timeout=timeout)
    if isinstance(status_payload, dict):
        instance["activeContext"] = status_payload.get("context") or instance["activeContext"]
        instance["apiUrl"] = status_payload.get("apiUrl") or instance["apiUrl"]
        instance["reachable"] = status_payload.get("reachable")
        health = status_payload.get("health")
        if isinstance(health, dict):
            instance["health"] = health.get("status")
        elif isinstance(health, str):
            instance["health"] = health
    else:
        warnings.append(
            issue(
                "STATUS_UNAVAILABLE",
                f"Could not parse `openship status`: {redact(status_result.stderr) or 'no JSON output'}",
                blocking=False,
            )
        )

    health_payload: Any | None = None
    env_from_status = isinstance(status_payload, dict) and isinstance(status_payload.get("env"), dict)
    if not env_from_status:
        health_result, health_payload = openship_json(binary, ["api", "/health/env"], cwd=cwd, timeout=timeout)
        if health_payload is None and health_result.returncode != 0:
            warnings.append(
                issue(
                    "CAPABILITY_DISCOVERY_FAILED",
                    f"Could not read /health/env: {redact(health_result.stderr) or 'no JSON output'}",
                    blocking=False,
                )
            )

    env_payload = pick_env(status_payload, health_payload)
    capabilities = capability_report(env_payload)
    if env_payload.get("selfHosted") is True:
        instance["mode"] = "self-hosted"
    elif env_payload.get("selfHosted") is False:
        instance["mode"] = "cloud"
    for key in ("deployMode", "authMode", "teamMode", "hostDomain", "machineName"):
        instance[key] = env_payload.get(key)

    if instance["reachable"] is None:
        instance["reachable"] = bool(instance["health"] or env_payload)
    if instance["reachable"] is False:
        warnings.append(
            issue(
                "API_UNREACHABLE",
                "The active context's API is not reachable. Local lifecycle/doctor work may still be possible.",
                blocking=False,
            )
        )
    if instance["authenticated"] is False:
        warnings.append(
            issue(
                "CONTEXT_NOT_AUTHENTICATED",
                "The active context does not report a stored token; authenticated operations may fail.",
                blocking=False,
            )
        )
    return cli, instance, contexts, capabilities


def build_report(cwd: Path, timeout: float) -> dict[str, Any]:
    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    repository, git_warnings = git_report(cwd, timeout)
    warnings.extend(git_warnings)

    project_link, project_link_error = read_project_link(cwd)
    if project_link_error:
        errors.append(project_link_error)
    elif not project_link["exists"]:
        warnings.append(
            issue(
                "PROJECT_LINK_MISSING",
                "No .openship/project.json was found; provide a project ID or run openship init before project-scoped writes.",
                blocking=False,
            )
        )
    elif not project_link.get("projectId"):
        errors.append(issue("PROJECT_ID_MISSING", "The project link does not contain a projectId.", blocking=True))

    binary = shutil.which("openship")
    cli: dict[str, Any] = {
        "installed": bool(binary),
        "path": binary,
        "version": None,
        "versionRaw": None,
    }
    instance = _initial_instance()
    contexts: list[dict[str, Any]] = []
    capabilities: dict[str, Any] = {}

    if not binary:
        errors.append(issue("OPENSHIP_NOT_INSTALLED", "The openship CLI is not available on PATH.", blocking=True))
    else:
        cli, instance, contexts, capabilities = _inspect_cli(
            binary, cwd=cwd, timeout=timeout, warnings=warnings
        )

    link_context = project_link.get("context")
    active_context = instance.get("activeContext")
    if link_context and active_context:
        matches = link_context == active_context
        project_link["contextMatches"] = matches
        if not matches:
            errors.append(
                issue(
                    "CONTEXT_MISMATCH",
                    f"Project link context {link_context!r} differs from active context {active_context!r}; block project-scoped writes.",
                    blocking=True,
                )
            )
    elif project_link.get("exists") and project_link.get("projectId"):
        warnings.append(
            issue(
                "CONTEXT_MATCH_UNKNOWN",
                "The project link exists but the active context could not be confirmed.",
                blocking=False,
            )
        )

    ready = not any(item.get("blocking") for item in errors)
    return {
        "schemaVersion": "0.1",
        "generatedAt": utc_now(),
        "ready": ready,
        "cli": cli,
        "instance": instance,
        "contexts": contexts,
        "repository": repository,
        "projectLink": project_link,
        "capabilities": capabilities,
        "warnings": warnings,
        "errors": errors,
    }
