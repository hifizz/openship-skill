"""Secret-exposure planning and local output sanitization for the Openship skill.

The module is deliberately independent of Openship's credential files. Repository
scans report paths, key names, pattern identifiers, and line numbers only. They
never return secret values or matching source snippets.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

SCHEMA_VERSION = "0.2"
MAX_SCAN_FILES = 750
MAX_CONFIG_BYTES = 1_000_000

SINK_STATUSES = {
    "unknown",
    "plaintext",
    "masked",
    "metadata-only",
    "sanitized-only",
    "write-only",
    "not-applicable",
}
SAFE_SINK_STATUSES = {
    "masked",
    "metadata-only",
    "sanitized-only",
    "write-only",
    "not-applicable",
}

SENSITIVE_KEY_RE = re.compile(
    r"(?i)(?:^|[_\-.])(?:"
    r"secret|token|password|passwd|pwd|api[_-]?key|private[_-]?key|"
    r"client[_-]?secret|access[_-]?key|database[_-]?url|redis[_-]?url|"
    r"smtp[_-]?(?:url|password)|dsn|credential|auth[_-]?(?:token|secret)"
    r")(?:$|[_\-.])"
)

ENV_FILE_RE = re.compile(r"^\.env(?:\.[A-Za-z0-9_-]+)?$")
ENV_EXAMPLE_MARKERS = ("example", "sample", "template", "dist", "defaults")
SENSITIVE_BASENAMES = {
    ".npmrc",
    ".pypirc",
    ".netrc",
    "credentials",
    "credentials.json",
    "service-account.json",
    "service_account.json",
    "id_rsa",
    "id_ed25519",
    "known_hosts",
}
SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"}

SCAN_NAMES = {
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    "package.json",
    "openship.json",
    "Makefile",
    "Procfile",
    "justfile",
    "Taskfile.yml",
    "Taskfile.yaml",
}
SCAN_SUFFIXES = {".sh", ".bash", ".zsh", ".fish", ".ps1", ".yml", ".yaml", ".json", ".toml"}
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".next",
    ".nuxt",
    "dist",
    "build",
    "coverage",
    ".venv",
    "venv",
    "__pycache__",
    ".cache",
    ".turbo",
}

OPERATION_SINKS: dict[str, tuple[str, ...]] = {
    "build": (
        "cliStdout",
        "cliStderr",
        "agentTranscript",
        "shellHistory",
        "buildLog",
        "dockerHistory",
        "buildArtifact",
        "apiResponse",
        "mcpResponse",
    ),
    "deploy": (
        "cliStdout",
        "cliStderr",
        "agentTranscript",
        "shellHistory",
        "buildLog",
        "runtimeLog",
        "dockerHistory",
        "buildArtifact",
        "apiResponse",
        "mcpResponse",
    ),
    "logs": (
        "cliStdout",
        "cliStderr",
        "agentTranscript",
        "requestedLog",
        "apiResponse",
        "mcpResponse",
    ),
    "env-read": (
        "cliStdout",
        "cliStderr",
        "agentTranscript",
        "apiResponse",
        "mcpResponse",
    ),
    "env-write": (
        "cliStdout",
        "cliStderr",
        "agentTranscript",
        "shellHistory",
        "secretInput",
        "apiResponse",
        "mcpResponse",
    ),
    "service-update": (
        "cliStdout",
        "cliStderr",
        "agentTranscript",
        "shellHistory",
        "runtimeLog",
        "apiResponse",
        "mcpResponse",
    ),
    "compose-sync": (
        "cliStdout",
        "cliStderr",
        "agentTranscript",
        "shellHistory",
        "buildLog",
        "runtimeLog",
        "dockerHistory",
        "apiResponse",
        "mcpResponse",
    ),
    "exec": (
        "cliStdout",
        "cliStderr",
        "agentTranscript",
        "execStdout",
        "execStderr",
        "runtimeLog",
        "apiResponse",
        "mcpResponse",
    ),
    "backup": (
        "cliStdout",
        "cliStderr",
        "agentTranscript",
        "jobLog",
        "backupArtifact",
        "apiResponse",
        "mcpResponse",
    ),
    "restore": (
        "cliStdout",
        "cliStderr",
        "agentTranscript",
        "jobLog",
        "runtimeLog",
        "apiResponse",
        "mcpResponse",
    ),
}

REMOTE_ENV_RELEVANT = {
    "build",
    "deploy",
    "logs",
    "env-read",
    "env-write",
    "service-update",
    "compose-sync",
    "exec",
    "backup",
    "restore",
}


@dataclass(frozen=True)
class PatternRule:
    code: str
    severity: str
    regex: re.Pattern[str]
    message: str


PATTERN_RULES: tuple[PatternRule, ...] = (
    PatternRule(
        "ENV_DUMP_COMMAND",
        "high",
        re.compile(r"(?i)(?<![A-Za-z0-9_.-])(?:printenv|env)(?=\s*(?:$|[;&|]))"),
        "Build or runtime command may print the complete process environment.",
    ),
    PatternRule(
        "SHELL_XTRACE",
        "high",
        re.compile(r"(?i)\b(?:set\s+-x|set\s+-o\s+xtrace|(?:ba|z|k)?sh\s+-x)\b"),
        "Shell tracing may echo expanded secret values into logs.",
    ),
    PatternRule(
        "PROCESS_ENV_SERIALIZATION",
        "high",
        re.compile(
            r"(?i)(?:console\.(?:log|dir|error)\s*\(\s*process\.env|"
            r"JSON\.stringify\s*\(\s*process\.env|"
            r"print\s*\(\s*(?:dict\s*\()?os\.environ|"
            r"pprint\s*\(\s*(?:dict\s*\()?os\.environ)"
        ),
        "Code may serialize the complete process environment.",
    ),
    PatternRule(
        "ENV_FILE_OUTPUT",
        "high",
        re.compile(r"(?i)\b(?:cat|type|Get-Content)\s+[^\n;&|]*\.env(?:\.[A-Za-z0-9_-]+)?\b"),
        "Command may print an environment file into logs.",
    ),
    PatternRule(
        "DOCKER_BUILD_ARG_SECRET",
        "high",
        re.compile(
            r"(?i)--build-arg(?:=|\s+)[A-Za-z_][A-Za-z0-9_]*(?:=|\s|$)|"
            r"^\s*ARG\s+[A-Za-z_][A-Za-z0-9_]*(?:=|\s|$)"
        ),
        "A Docker build argument may carry sensitive data into build output or image history.",
    ),
    PatternRule(
        "CREDENTIAL_URL_LITERAL",
        "high",
        re.compile(r"(?i)\b(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis|amqp)://[^\s/:@]+:[^\s/@]+@"),
        "A credential-bearing connection URL appears in build or deployment configuration.",
    ),
    PatternRule(
        "PRIVATE_KEY_LITERAL",
        "critical",
        re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"),
        "A private key appears inline in a scanned configuration file.",
    ),
)

SENSITIVE_VAR_REFERENCE_RE = re.compile(
    r"(?i)(?:\$\{?|%)([A-Za-z_][A-Za-z0-9_]*(?:SECRET|TOKEN|PASSWORD|PASSWD|PWD|API_KEY|PRIVATE_KEY|DATABASE_URL|REDIS_URL)[A-Za-z0-9_]*)\}?%?"
)
ECHO_RE = re.compile(r"(?i)\b(?:echo|printf|Write-Output|console\.(?:log|error))\b")
DOCKER_ARG_RE = re.compile(r"(?i)^\s*(ARG|ENV)\s+([A-Za-z_][A-Za-z0-9_]*)")


# Output-redaction patterns. Reports contain category/count only; match values are
# never copied into diagnostics.
PRIVATE_KEY_BLOCK_RE = re.compile(
    r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----.*?-----END (?:[A-Z0-9 ]+ )?PRIVATE KEY-----",
    re.DOTALL,
)
DATABASE_URL_RE = re.compile(
    r"(?i)\b(?P<scheme>postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis|rediss|amqp|amqps)://"
    r"(?P<user>[^\s/:@]+):(?P<password>[^\s/@]+)@"
)
BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
TOKEN_PREFIX_RE = re.compile(
    r"\b(?:opsh_[A-Za-z0-9_-]{8,}|github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16})\b"
)
JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
QUERY_SECRET_RE = re.compile(
    r"(?i)(?P<prefix>[?&](?:access_token|api[_-]?key|token|secret|password)=)(?P<value>[^&#\s]+)"
)
ASSIGNMENT_RE = re.compile(
    r"(?im)(?P<prefix>(?:^|[,{\s])(?:[\"']?)[A-Za-z0-9_.-]*"
    r"(?:SECRET|TOKEN|PASSWORD|PASSWD|API[_-]?KEY|PRIVATE[_-]?KEY|CLIENT[_-]?SECRET|DATABASE[_-]?URL|REDIS[_-]?URL)"
    r"[A-Za-z0-9_.-]*(?:[\"']?)\s*[:=]\s*)(?P<quote>[\"']?)(?P<value>[^\n,}\s]+|[^\"'\n]*)(?P=quote)"
)


def is_sensitive_key(name: str) -> bool:
    return bool(SENSITIVE_KEY_RE.search(name.strip()))


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def _is_env_file(path: Path) -> bool:
    name = path.name
    if not ENV_FILE_RE.match(name):
        return False
    lowered = name.lower()
    return not any(marker in lowered for marker in ENV_EXAMPLE_MARKERS)


def _sensitive_file_kind(path: Path) -> str | None:
    name = path.name
    lowered = name.lower()
    if _is_env_file(path):
        return "environment-file"
    if lowered in SENSITIVE_BASENAMES:
        return "credential-file"
    if path.suffix.lower() in SENSITIVE_SUFFIXES:
        return "key-or-keystore"
    return None


def _should_scan_text(path: Path) -> bool:
    name = path.name
    if name in SCAN_NAMES or name.startswith("Dockerfile"):
        return True
    if ".github" in path.parts and "workflows" in path.parts and path.suffix.lower() in {".yml", ".yaml"}:
        return True
    if "scripts" in path.parts and path.suffix.lower() in SCAN_SUFFIXES:
        return True
    return False


def iter_repository_files(root: Path) -> Iterator[Path]:
    yielded = 0
    for current_root, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
        base = Path(current_root)
        for filename in files:
            path = base / filename
            if path.is_symlink():
                continue
            yield path
            yielded += 1
            if yielded >= MAX_SCAN_FILES:
                return


def extract_env_keys(path: Path) -> tuple[list[str], str | None]:
    """Read only key names from an env file and discard values immediately."""

    try:
        if path.stat().st_size > MAX_CONFIG_BYTES:
            return [], "file-too-large"
        keys: list[str] = []
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for raw_line in handle:
                line = raw_line.lstrip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[7:].lstrip()
                if "=" not in line:
                    continue
                key = line.split("=", 1)[0].strip()
                if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", key):
                    keys.append(key)
        return sorted(set(keys)), None
    except OSError:
        return [], "unreadable"


def _finding(code: str, severity: str, path: str, line: int, message: str, *, key: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "code": code,
        "severity": severity,
        "path": path,
        "line": line,
        "message": message,
    }
    if key:
        result["key"] = key
    return result


def scan_config_file(path: Path, root: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    relative = _relative(path, root)
    try:
        if path.stat().st_size > MAX_CONFIG_BYTES:
            return [
                _finding(
                    "CONFIG_NOT_SCANNED_SIZE",
                    "medium",
                    relative,
                    0,
                    "Configuration file exceeded the static-scan size limit.",
                )
            ]
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_number, line in enumerate(handle, start=1):
                for rule in PATTERN_RULES:
                    if rule.regex.search(line):
                        # Docker ARG is only a high-confidence secret issue when the
                        # declared key is sensitive; generic --build-arg still merits
                        # a medium finding.
                        severity = rule.severity
                        code = rule.code
                        message = rule.message
                        key: str | None = None
                        if code == "DOCKER_BUILD_ARG_SECRET":
                            declared = DOCKER_ARG_RE.search(line)
                            build_arg = re.search(r"(?i)--build-arg(?:=|\s+)([A-Za-z_][A-Za-z0-9_]*)", line)
                            key = (declared or build_arg).group(2 if declared else 1) if (declared or build_arg) else None
                            if key and not is_sensitive_key(key):
                                severity = "medium"
                                code = "DOCKER_BUILD_ARG_REVIEW"
                                message = "Docker build arguments can be persisted or echoed; verify this argument is non-secret."
                        findings.append(_finding(code, severity, relative, line_number, message, key=key))

                references = SENSITIVE_VAR_REFERENCE_RE.findall(line)
                if references and ECHO_RE.search(line):
                    for key in sorted(set(references)):
                        findings.append(
                            _finding(
                                "SENSITIVE_VALUE_ECHO",
                                "high",
                                relative,
                                line_number,
                                "Command may print a sensitive environment variable.",
                                key=key,
                            )
                        )

                declared = DOCKER_ARG_RE.search(line)
                if declared and is_sensitive_key(declared.group(2)):
                    findings.append(
                        _finding(
                            "DOCKER_SECRET_DECLARATION",
                            "high",
                            relative,
                            line_number,
                            "Sensitive data declared through Docker ARG/ENV may leak into logs, history, or layers.",
                            key=declared.group(2),
                        )
                    )
    except OSError:
        findings.append(
            _finding(
                "CONFIG_NOT_SCANNED_UNREADABLE",
                "medium",
                relative,
                0,
                "Configuration file could not be read for the exposure scan.",
            )
        )
    return _dedupe_findings(findings)


def _dedupe_findings(findings: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[tuple[Any, ...], dict[str, Any]] = {}
    for item in findings:
        key = (item.get("code"), item.get("path"), item.get("line"), item.get("key"))
        unique[key] = item
    return sorted(unique.values(), key=lambda item: (item.get("path", ""), item.get("line", 0), item.get("code", "")))


def scan_repository(root: Path) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    scanned_files = 0
    visited_files = 0

    for path in iter_repository_files(root):
        visited_files += 1
        kind = _sensitive_file_kind(path)
        if kind:
            keys: list[str] = []
            note: str | None = None
            inspection = "name-only"
            if kind == "environment-file":
                keys, note = extract_env_keys(path)
                inspection = "keys-only"
            source: dict[str, Any] = {
                "type": kind,
                "path": _relative(path, root),
                "inspection": inspection,
                "valuesReturned": False,
            }
            if keys:
                source["keys"] = keys
                source["sensitiveKeys"] = [key for key in keys if is_sensitive_key(key)]
            if note:
                source["note"] = note
            sources.append(source)

        if _should_scan_text(path):
            scanned_files += 1
            findings.extend(scan_config_file(path, root))

    return {
        "root": str(root),
        "visitedFiles": visited_files,
        "scannedConfigFiles": scanned_files,
        "sources": sorted(sources, key=lambda item: item["path"]),
        "findings": _dedupe_findings(findings),
        "scanLimitReached": visited_files >= MAX_SCAN_FILES,
    }


def load_evidence(path: Path | None) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    if path is None:
        return {}, []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read evidence file: {type(exc).__name__}") from exc
    sinks = data.get("sinks")
    if not isinstance(sinks, Mapping):
        raise ValueError("Evidence file must contain an object named 'sinks'")

    normalized: dict[str, dict[str, Any]] = {}
    evidence: list[dict[str, Any]] = []
    for name, raw in sinks.items():
        if isinstance(raw, str):
            item = {"status": raw, "method": "evidence-file"}
        elif isinstance(raw, Mapping):
            item = {str(key): value for key, value in raw.items() if key in {"status", "method", "verifiedAt", "scope", "note"}}
        else:
            raise ValueError(f"Evidence sink '{name}' must be a string or object")
        status = item.get("status")
        if status not in SINK_STATUSES:
            raise ValueError(f"Unsupported evidence status for '{name}': {status}")
        normalized[str(name)] = item
        evidence.append({"sink": str(name), **item})
    return normalized, evidence


def _default_sinks(operation: str) -> dict[str, dict[str, Any]]:
    if operation not in OPERATION_SINKS:
        raise ValueError(f"Unsupported operation: {operation}")
    result: dict[str, dict[str, Any]] = {}
    for name in OPERATION_SINKS[operation]:
        status = "sanitized-only" if name == "agentTranscript" else "unknown"
        result[name] = {"status": status, "evidence": "default-fail-closed"}
    return result


def build_exposure_plan(
    *,
    root: Path,
    operation: str,
    remote_env_state: str,
    evidence_file: Path | None = None,
    sensitive_keys: Sequence[str] = (),
) -> dict[str, Any]:
    if remote_env_state not in {"unknown", "none", "present"}:
        raise ValueError("remote_env_state must be one of: unknown, none, present")

    scan = scan_repository(root)
    sources = list(scan["sources"])
    declared_keys = sorted({key for key in sensitive_keys if key})

    if operation in REMOTE_ENV_RELEVANT:
        remote_source: dict[str, Any] = {
            "type": "openship-remote-environment",
            "state": remote_env_state,
            "valuesReturned": False,
        }
        if declared_keys:
            remote_source["keys"] = declared_keys
        sources.append(remote_source)

    sinks = _default_sinks(operation)
    evidence_map, evidence = load_evidence(evidence_file)
    for name, item in evidence_map.items():
        if name in sinks:
            sinks[name] = {
                "status": item["status"],
                "evidence": item.get("method", "evidence-file"),
                **({"verifiedAt": item["verifiedAt"]} if item.get("verifiedAt") else {}),
                **({"scope": item["scope"]} if item.get("scope") else {}),
            }

    local_sensitive = bool(scan["sources"])
    remote_sensitive = operation in REMOTE_ENV_RELEVANT and remote_env_state in {"unknown", "present"}
    touches_sensitive = local_sensitive or remote_sensitive or bool(declared_keys)

    findings = scan["findings"]
    severe_findings = [item for item in findings if item["severity"] in {"high", "critical"}]
    plaintext_sinks = [name for name, item in sinks.items() if item["status"] == "plaintext"]
    unknown_sinks = [name for name, item in sinks.items() if item["status"] == "unknown"]
    blocking_unknown_sinks = [
        name for name in unknown_sinks if not (operation == "env-write" and name == "secretInput")
    ]

    blocking_reasons: list[str] = []
    required_actions: list[str] = []

    if scan["scanLimitReached"]:
        blocking_reasons.append("Repository scan reached its file limit; sensitive sources may be unclassified.")
        required_actions.append("Narrow the working directory or review excluded files before the operation.")
    if severe_findings:
        blocking_reasons.append("High-confidence output-leak patterns exist in build or deployment configuration.")
        required_actions.append("Remove or safely replace every high/critical finding before running the operation.")
    if operation in REMOTE_ENV_RELEVANT and remote_env_state == "unknown":
        blocking_reasons.append("The presence of secrets in the selected Openship environment is unknown.")
        required_actions.append("Query secret-safe environment metadata and rerun with remote-env-state none or present.")
    if plaintext_sinks:
        blocking_reasons.append("One or more output sinks are verified to expose plaintext sensitive data.")
        required_actions.append("Change the execution path or output behavior; redaction after persistence is not sufficient.")
    if touches_sensitive and blocking_unknown_sinks:
        blocking_reasons.append("Sensitive data may be touched while one or more output sinks remain unverified.")
        required_actions.append("Provide live-schema or disposable-canary evidence for every relevant unknown sink.")

    decision = "allow"
    if blocking_reasons:
        decision = "blocked"
    elif operation == "env-write" and touches_sensitive and sinks.get("secretInput", {}).get("status") != "write-only":
        decision = "require-out-of-band-entry"
        required_actions.append("Use an interactive/write-only secret input path and keep the value out of command arguments and transcripts.")
    elif touches_sensitive or findings:
        decision = "allow-with-redaction"

    return {
        "schemaVersion": SCHEMA_VERSION,
        "operation": operation,
        "repository": {
            "root": scan["root"],
            "visitedFiles": scan["visitedFiles"],
            "scannedConfigFiles": scan["scannedConfigFiles"],
            "scanLimitReached": scan["scanLimitReached"],
        },
        "touchesSensitiveData": touches_sensitive,
        "sources": sources,
        "findings": findings,
        "sinks": sinks,
        "evidence": evidence,
        "decision": decision,
        "blockingReasons": sorted(set(blocking_reasons)),
        "requiredActions": sorted(set(required_actions)),
    }


def sanitize_text(text: str, *, canaries: Sequence[str] = ()) -> tuple[str, dict[str, int]]:
    """Redact common credential forms without returning matched values."""

    value = text or ""
    counts: Counter[str] = Counter()

    for canary in canaries:
        if not canary:
            continue
        occurrences = value.count(canary)
        if occurrences:
            value = value.replace(canary, "<redacted:canary>")
            counts["canary"] += occurrences

    value, count = PRIVATE_KEY_BLOCK_RE.subn("<redacted:private-key>", value)
    counts["private-key"] += count

    def redact_database_url(match: re.Match[str]) -> str:
        counts["credential-url"] += 1
        return f"{match.group('scheme')}://{match.group('user')}:<redacted>@"

    value = DATABASE_URL_RE.sub(redact_database_url, value)

    value, count = BEARER_RE.subn("Bearer <redacted>", value)
    counts["bearer-token"] += count

    value, count = TOKEN_PREFIX_RE.subn("<redacted:token>", value)
    counts["token"] += count

    value, count = JWT_RE.subn("<redacted:jwt>", value)
    counts["jwt"] += count

    def redact_query(match: re.Match[str]) -> str:
        counts["query-secret"] += 1
        return match.group("prefix") + "<redacted>"

    value = QUERY_SECRET_RE.sub(redact_query, value)

    def redact_assignment(match: re.Match[str]) -> str:
        counts["sensitive-assignment"] += 1
        return match.group("prefix") + "<redacted>"

    value = ASSIGNMENT_RE.sub(redact_assignment, value)
    return value, dict(sorted((key, amount) for key, amount in counts.items() if amount))


def safe_diagnostic(text: str, *, max_chars: int = 600) -> str:
    sanitized, _ = sanitize_text(text)
    sanitized = sanitized.strip()
    if len(sanitized) > max_chars:
        return sanitized[: max_chars - 1] + "…"
    return sanitized
