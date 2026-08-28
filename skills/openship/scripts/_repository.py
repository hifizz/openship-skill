"""Repository and .openship/project.json inspection."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from _runtime import command_text, issue, redact, run_command


def find_upward(start: Path, relative: Path) -> Path | None:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    while True:
        candidate = current / relative
        if candidate.exists():
            return candidate
        if current.parent == current:
            return None
        current = current.parent


def _empty_link(*, exists: bool, path: str | None) -> dict[str, Any]:
    return {
        "exists": exists,
        "path": path,
        "projectId": None,
        "name": None,
        "slug": None,
        "context": None,
        "environment": None,
        "branch": None,
        "contextMatches": None,
    }


def read_project_link(cwd: Path) -> tuple[dict[str, Any], dict[str, Any] | None]:
    path = find_upward(cwd, Path(".openship") / "project.json")
    if path is None:
        return _empty_link(exists=False, path=None), None

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _empty_link(exists=True, path=str(path)), issue(
            "PROJECT_LINK_INVALID",
            f"Could not parse {path}: {redact(str(exc))}",
            blocking=True,
        )

    if not isinstance(raw, dict):
        return _empty_link(exists=True, path=str(path)), issue(
            "PROJECT_LINK_INVALID", f"{path} must contain a JSON object.", blocking=True
        )

    defaults = raw.get("defaults") if isinstance(raw.get("defaults"), dict) else {}
    return {
        "exists": True,
        "path": str(path),
        "projectId": raw.get("projectId") if isinstance(raw.get("projectId"), str) else None,
        "name": raw.get("name") if isinstance(raw.get("name"), str) else None,
        "slug": raw.get("slug") if isinstance(raw.get("slug"), str) else None,
        "context": raw.get("context") if isinstance(raw.get("context"), str) else None,
        "environment": defaults.get("environment")
        if isinstance(defaults.get("environment"), str)
        else None,
        "branch": raw.get("branch") if isinstance(raw.get("branch"), str) else None,
        "contextMatches": None,
    }, None


def git_report(cwd: Path, timeout: float) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    git = shutil.which("git")
    report: dict[str, Any] = {
        "cwd": str(cwd.resolve()),
        "gitInstalled": bool(git),
        "isGitRepository": False,
        "root": None,
        "branch": None,
        "head": None,
        "dirty": None,
        "changeCount": None,
    }
    if not git:
        warnings.append(issue("GIT_NOT_INSTALLED", "git is not available; repository state could not be inspected.", blocking=False))
        return report, warnings

    inside = run_command([git, "-C", str(cwd), "rev-parse", "--is-inside-work-tree"], cwd=cwd, timeout=timeout)
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        warnings.append(issue("NOT_A_GIT_REPOSITORY", "The working directory is not inside a Git repository.", blocking=False))
        return report, warnings

    root_result = run_command([git, "-C", str(cwd), "rev-parse", "--show-toplevel"], cwd=cwd, timeout=timeout)
    root_text = command_text(root_result)
    root = Path(root_text).resolve() if root_result.returncode == 0 and root_text else cwd.resolve()

    branch_result = run_command([git, "-C", str(root), "branch", "--show-current"], cwd=root, timeout=timeout)
    head_result = run_command([git, "-C", str(root), "rev-parse", "HEAD"], cwd=root, timeout=timeout)
    status_result = run_command([git, "-C", str(root), "status", "--porcelain"], cwd=root, timeout=timeout)
    changes = [line for line in status_result.stdout.splitlines() if line.strip()] if status_result.returncode == 0 else []
    branch = command_text(branch_result)
    head = command_text(head_result)

    report.update(
        {
            "isGitRepository": True,
            "root": str(root),
            "branch": branch or ("DETACHED" if head else None),
            "head": head,
            "dirty": bool(changes) if status_result.returncode == 0 else None,
            "changeCount": len(changes) if status_result.returncode == 0 else None,
        }
    )
    if changes:
        warnings.append(
            issue(
                "WORKTREE_DIRTY",
                f"The repository has {len(changes)} uncommitted change(s); Git deployments normally exclude them.",
                blocking=False,
            )
        )
    return report, warnings
