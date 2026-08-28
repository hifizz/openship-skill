---
name: openship
description: Operate and troubleshoot Openship projects, deployments, services, domains, servers, backups, and self-hosted instances through the local `openship` CLI, authenticated REST API, and MCP capability catalog. Use when a user asks to deploy to OpenShip/Openship, link the current repository, inspect or modify Openship projects/services/environment variables/domains, diagnose deployment or instance failures, manage self-hosted Openship infrastructure, or author and validate `openship.json` as part of an operational task. Do not use for OpenShift or generic Docker/Kubernetes work unless the resources are explicitly managed through Openship.
---

# Openship Operator

Treat Openship as an API-backed control plane. Use the CLI as the primary local operator interface, `openship api` for authenticated REST coverage, MCP for live capability/schema discovery, and the UI only for flows that are intentionally out of band.

Do not act from memory alone. Openship evolves quickly; discover the current installed and connected capabilities before choosing commands or request bodies.

## Operating contract

Follow this loop for every task:

1. **Discover** the CLI, active context, instance mode, repository, and project link.
2. **Resolve** exact resource identities. Prefer IDs over names for mutations.
3. **Inspect** current state before changing it.
4. **Plan** the smallest change and identify blast radius, persistence, and rollback.
5. **Guard** the action using the risk and secret rules below.
6. **Execute** through the narrowest supported channel.
7. **Verify** by reading state, status, health, URLs, or logs after the change.
8. **Report** the target, action, result, evidence, and remaining risk.

Never substitute a successful process exit for verification.

## Start with preflight

Run the bundled helper from the skill directory or address it by absolute path:

```bash
python3 scripts/preflight.py --cwd "$PWD"
```

Inspect these fields before mutation:

- `cli.version`
- `instance.activeContext`
- `instance.reachable`
- `instance.mode`
- `repository.root` and `repository.branch`
- `projectLink.projectId`
- `projectLink.contextMatches`
- `errors` and `warnings`

If the helper cannot be located, gather the same information with:

```bash
openship --version
openship --json status
openship --json context list
git rev-parse --show-toplevel
git status --short --branch
```

Do not read `~/.openship/config.json`; it contains credentials.

## Use the live source-of-truth order

When information conflicts, use this precedence:

1. current `openship <command> --help` and `openship --version`;
2. current instance responses, `/health/env`, and MCP `tools/list` schemas;
3. current official Openship documentation and source;
4. bundled references in this skill.

Treat bundled examples as patterns, not a promise that every option exists in every version.

## Resolve the target safely

Use this identity order:

1. explicit resource ID supplied by the user;
2. the nearest `.openship/project.json` found by walking upward from the working directory;
3. a unique slug;
4. a unique exact name returned by a list operation.

Do not mutate when a name resolves to zero or multiple resources. List candidates and require an ID or unique target.

Compare the project link's `context` with the CLI's active context. A mismatch is blocking for writes because a repository can be linked under one context while the CLI currently points to another instance.

For a mismatch:

- allow narrowly scoped reads only after stating which context is active;
- do not silently switch contexts;
- switch only when the user has clearly selected the destination;
- rerun preflight after switching.

See [references/model.md](references/model.md) for the resource model and [references/safety.md](references/safety.md) for the complete context guard.

## Route execution through four channels

### 1. Dedicated CLI

Prefer a dedicated command when it exists. It usually provides the safest project-link resolution, folder upload, streaming, interactive confirmation, and platform-specific behavior.

Before using a command whose options matter, inspect live help:

```bash
openship <command> --help
openship <command> <subcommand> --help
```

Prefer machine-readable output for reads:

```bash
openship --json <command> ...
```

Use dedicated CLI commands for common instance, context, project, service, domain, deployment, log, server, system, mail, and backup workflows.

### 2. Authenticated REST through `openship api`

Use `openship api` when no dedicated command exposes the required route or when an exact JSON response/body is needed:

```bash
openship --json api /projects
openship --json api /projects/proj_xxx/services/svc_xxx
openship --json api /path --method PATCH --data '{"field":"value"}'
```

Do not guess a path or body. Discover it from current help, current official routes/docs, or the live MCP schema first.

Use `openship api` instead of raw `curl` so the active context and credential handling stay inside Openship. Use an external HTTP client only for an explicitly out-of-band binary upload returned by the platform.

### 3. MCP capability catalog

Use MCP to learn what the current token and instance can actually expose. Run:

```bash
python3 scripts/mcp_catalog.py --kind tools
python3 scripts/mcp_catalog.py --kind tools --search service
python3 scripts/mcp_catalog.py --kind prompts
```

Use returned `inputSchema`, `readOnly`, and `destructive` metadata to plan calls. A tool being listed means it may succeed for some authorized input; the real API still rechecks permission for the selected resource.

Do not treat MCP as a way around permissions, credential restrictions, or routes intentionally omitted from automation.

### 4. UI or out-of-band flow

Stop and surface the required user step when Openship returns an OAuth URL, `flowHref`, browser-only authorization, interactive PTY flow, or binary upload instruction that the current channel cannot complete safely.

Do not fabricate an API equivalent for a UI-only flow.

See [references/routing.md](references/routing.md) and [references/api-and-mcp.md](references/api-and-mcp.md).

## Classify risk before mutation

Assign one level before execution:

- **R0 — read-only:** list/get/status/health/logs/config inspection.
- **R1 — routine reversible:** deploy a selected commit, link a repo, add a normal domain, restart a stateless service.
- **R2 — stateful or infrastructure:** change image/ports/network/volumes, Compose sync, database changes, server/edge/mail/backup configuration.
- **R3 — destructive or privileged:** delete, wipe volumes, restore/migrate, reset admin, uninstall, arbitrary container exec, host-level command.

Apply these rules:

- R0: execute directly and summarize evidence.
- R1: execute when the target and desired result are explicit; verify afterward.
- R2: inspect dependencies, persistence, backup, data compatibility, and rollback first. State the plan before executing.
- R3: require exact identity, explicit authorization for the destructive effect, and a clear blast-radius statement. Never infer consent from “clean up,” “fix it,” or similar vague language.

See [references/safety.md](references/safety.md).

## Enforce hard safety rules

### Protect credentials and secrets

- Never read or print `~/.openship/config.json`.
- Never echo a PAT, bearer header, secret environment value, or credential file.
- Treat masked values such as `••••••••` or `__OPENSHIP_MASKED__` as sentinels, not real values.
- Preserve an existing masked secret unless the user explicitly supplies a replacement.
- Do not write secrets into `openship.json`, source control, command history, logs, or reports.
- Prefer Openship's secret-aware environment APIs/CLI over shell interpolation.

### Read before PATCH

Fetch the complete current resource before partial updates.

For services, treat `environment` and `advanced` as merge-like only when the live schema confirms it. Treat arrays such as `ports`, `volumes`, `dependsOn`, and `publicEndpoints` as whole-value replacements unless the live schema states otherwise. Build the complete desired array before PATCH.

Never “add one volume” by sending only the new volume to a replacement field.

### Protect stateful services

Before changing a database, queue, object store, or any service with persistent volumes:

1. identify the exact service and project;
2. list current image, command, environment keys, ports, volumes, dependencies, and health;
3. identify volume names and whether other projects/services share them;
4. check backup availability and restore procedure;
5. verify image/extension/data compatibility;
6. distinguish container replacement from volume deletion;
7. state rollback steps;
8. execute only the minimum change;
9. verify data and health after recreation.

Never delete or replace a persistent volume merely to resolve an image or extension problem.

### Treat restart and config application differently

A container restart may bounce the current container without applying changed environment or configuration. If Openship reports stale service config, use the current supported refresh/redeploy path for the selected service rather than repeatedly restarting it.

### Restrict exec

Use logs, health, configuration, deployment state, and volume metadata before container exec.

Treat exec as R3 because it runs shell commands inside a service. Use it only when the user explicitly requests it or read-only diagnostics cannot answer the question. Avoid commands that enumerate secrets, mutate databases, delete files, or change package state unless separately authorized and backed by a rollback plan.

### Handle pending actions exactly

A deployment in `pending` or `action_required` is not automatically failed. Read the deployment's pending actions and use only server-provided action IDs and allowed resolutions. Never guess an action ID or resolution payload.

## Work by domain

Load only the relevant reference before non-trivial work:

- Projects, linking, env, config: [references/projects.md](references/projects.md)
- Deployments, logs, pending actions: [references/deployments.md](references/deployments.md)
- Services, Compose, volumes, databases: [references/services.md](references/services.md)
- Servers, instance lifecycle, backups, edge, mail: [references/infrastructure.md](references/infrastructure.md)
- API, MCP, permissions, schemas: [references/api-and-mcp.md](references/api-and-mcp.md)
- Failure diagnosis: [references/troubleshooting.md](references/troubleshooting.md)

## Verify every change

Choose verification that proves the requested outcome:

- project update: GET the project and compare the intended fields;
- env update: list keys and metadata without revealing values;
- service update: GET the service, inspect drift/stale state, then check container health;
- deploy: follow status to a terminal state, inspect logs on failure, and probe returned URLs when appropriate;
- domain: read domain/certificate/routing status;
- backup: read the backup record and artifact status;
- restore/migration: verify service health and application data, not only job completion;
- instance repair/update: rerun `status` and `doctor`.

Do not report success while the platform still shows `queued`, `building`, `pending`, `action_required`, `degraded`, or an equivalent non-terminal state.

## Report in a compact operational record

Return:

```text
Target: <context / instance / project / service>
Risk: <R0-R3>
Observed: <relevant initial state>
Action: <exact channel and change>
Result: <terminal status and identifiers>
Verified by: <read-back, health, logs, or endpoint evidence>
Remaining risk: <none or explicit follow-up>
```

Redact secrets and avoid dumping large raw JSON or logs. Quote only the lines needed to establish the result.

## Stop conditions

Stop rather than improvise when:

- the active context and project link disagree for a write;
- the target is ambiguous;
- the current CLI/schema cannot confirm a requested option or body;
- a mutation would replace unknown arrays or masked secrets;
- a stateful change lacks enough information to preserve data;
- a destructive action lacks explicit authorization;
- the platform returns an out-of-band authorization or user-decision flow;
- evidence suggests an Openship platform defect rather than user configuration.

For suspected platform defects, preserve the command/tool name, sanitized arguments, version, resource IDs, status, and error text so the user can file a reproducible upstream issue.
