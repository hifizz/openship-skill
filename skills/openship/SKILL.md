---
name: openship
description: Operate and troubleshoot Openship projects, deployments, services, domains, servers, backups, and self-hosted instances through the local `openship` CLI, authenticated REST API, and MCP capability catalog. Use when a user asks to deploy to OpenShip/Openship, link the current repository, inspect or modify Openship projects/services/environment variables/domains, diagnose deployment or instance failures, manage self-hosted Openship infrastructure, or author and validate `openship.json` as part of an operational task. Do not use for OpenShift or generic Docker/Kubernetes work unless the resources are explicitly managed through Openship.
---

# Openship Operator

Treat Openship as an API-backed control plane. Use the CLI as the primary local operator interface, `openship api` for authenticated REST coverage, MCP for live capability/schema discovery, and the UI only for flows that are intentionally out of band.

Do not act from memory alone. Discover the installed CLI and connected instance before selecting commands, schemas, request bodies, or safety assumptions.

## Non-negotiable security invariant

No plaintext user secret may enter model context, a displayed command, a persisted operation record, or an unverified output sink.

Prevent emission first. Redaction after a value has reached an Openship/Docker/CI log, API response, tool result, artifact, or Agent transcript does not undo the exposure. Never use a real credential to test output safety.

## Operating contract

Follow this loop for every task:

1. **Discover** the CLI, active context, instance mode, repository, project link, and capabilities.
2. **Resolve** exact resource identities. Prefer IDs over names for mutations.
3. **Inspect** current state before changing it.
4. **Plan** the smallest change, blast radius, persistence, rollback, and verification.
5. **Guard** the action using context, risk, stateful-data, and secret-exposure rules.
6. **Execute** through the narrowest supported channel.
7. **Verify** by reading state, status, health, URLs, bounded sanitized logs, or application behavior.
8. **Report** the target, action, result, evidence, and remaining risk without secrets.

Never substitute a successful process exit for verification.

## Start with context preflight

Run:

```bash
python3 scripts/preflight.py --cwd "$PWD"
```

Inspect at least:

- `cli.version`;
- `instance.activeContext`, `apiUrl`, `reachable`, and `mode`;
- `repository.root`, `branch`, `head`, and dirty status;
- `projectLink.projectId`, `context`, and `contextMatches`;
- `errors` and `warnings`.

If the helper cannot be located, gather the same information with current CLI help/output:

```bash
openship --version
openship --json status
openship --json context list
git rev-parse --show-toplevel
git status --short --branch
```

Never read `~/.openship/config.json`; it contains credentials.

## Run the Secret Exposure Gate before build or sensitive work

The gate is mandatory before:

- build or deploy;
- build/runtime log retrieval;
- environment-variable list/read/write;
- Service/Compose/image/command/build-arg changes;
- container exec;
- database commands that may print a connection URL;
- backup/restore jobs;
- API/MCP calls that may return environment values.

Run:

```bash
python3 scripts/secret_exposure_preflight.py \
  --cwd "$PWD" \
  --operation deploy \
  --remote-env-state unknown \
  --fail-closed
```

Before build/deploy, classify the selected Openship environment through key/secret metadata only:

- `none`: verified to contain no sensitive variables;
- `present`: one or more sensitive variables exist, without retrieving values;
- `unknown`: not yet established; this is blocking.

When secrets may be touched, every relevant output sink must be proven `masked`, `metadata-only`, `write-only`, `sanitized-only`, or `not-applicable` by live schema/current official source or a disposable fake-canary test. Unknown or plaintext behavior is blocking.

For a new secret, prefer an interactive/write-only or Dashboard entry flow. Do not put the value in the Agent conversation, displayed command, JSON command argument, source file, log, or journal. If no safe input path is proven, stop with `require-out-of-band-entry`.

Before presenting a bounded CLI/API/log payload, sanitize it locally:

```bash
some-command 2>&1 | python3 scripts/log_leak_scan.py --fail-on-detection
```

This protects only the displayed output; it does not prove that the upstream raw log was safe. See [references/secrets.md](references/secrets.md).

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
2. the nearest `.openship/project.json` found by walking upward;
3. a unique slug;
4. a unique exact name returned by a list operation.

Do not mutate when a name resolves to zero or multiple resources. List candidates and require an ID or unique target.

Compare the project link's context with the CLI's active context. A mismatch is blocking for writes because the link can refer to one instance while the CLI targets another.

For a mismatch:

- allow narrowly scoped reads only after stating the active context;
- do not silently switch;
- switch only when the user clearly selected the destination;
- rerun both context and secret-exposure preflight after switching.

See [references/model.md](references/model.md) and [references/safety.md](references/safety.md).

## Route execution through four channels

### 1. Dedicated CLI

Prefer a dedicated command when it exists. It usually handles project-link resolution, folder upload, streaming, interactive confirmation, and platform-specific behavior more safely.

Before using version-sensitive options:

```bash
openship <command> --help
openship <command> <subcommand> --help
```

Prefer machine-readable reads:

```bash
openship --json <command> ...
```

Do not display commands containing secret values.

### 2. Authenticated REST through `openship api`

Use `openship api` when no dedicated command exposes the required route or an exact JSON response/body is necessary:

```bash
openship --json api /projects
openship --json api /projects/proj_xxx/services/svc_xxx
```

Do not guess a route or body. Discover it from current help, official routes/docs, or live MCP schema first.

Use `openship api` instead of raw `curl` so active context and credentials remain inside Openship. Never embed a secret in a displayed `--data` argument. Use an external HTTP client only for an explicitly out-of-band binary upload returned by the platform.

### 3. MCP capability catalog

Use MCP to learn which tools the current token and instance expose:

```bash
python3 scripts/mcp_catalog.py --kind tools
python3 scripts/mcp_catalog.py --kind tools --search service
python3 scripts/mcp_catalog.py --kind prompts
```

Use returned `inputSchema`, `readOnly`, and `destructive` metadata. A listed tool is still re-authorized against the selected resource. Do not invoke an environment-related tool until its response and logging behavior pass the Secret Exposure Gate.

### 4. UI or out-of-band flow

Stop and surface the user step when Openship returns OAuth, `flowHref`, browser-only authorization, interactive PTY, binary upload, or write-only secret entry that the current channel cannot complete safely.

Do not fabricate an API equivalent for a UI-only flow.

See [references/routing.md](references/routing.md) and [references/api-and-mcp.md](references/api-and-mcp.md).

## Classify risk before mutation

Assign one level:

- **R0 — read-only:** list/get/status/health and verified metadata-only inspection;
- **R1 — routine reversible:** deploy a selected commit, link a repo, add a normal domain, restart a known stateless service;
- **R2 — stateful or infrastructure:** image/port/network/volume/Compose/database/server/edge/mail/backup changes;
- **R3 — destructive or privileged:** delete, wipe volumes, restore/migrate, reset admin, uninstall, container exec, host command.

Secret-sensitive reads can be operationally R0 but remain blocked until their output surfaces are verified. Risk level never overrides the Secret Exposure Gate.

Apply:

- R0: execute directly only when targeting and output behavior are safe;
- R1: execute when target/result are explicit, then verify;
- R2: inspect dependencies, persistence, backup, compatibility, and rollback; state the plan before execution;
- R3: require exact identity, explicit authorization for the destructive/privileged effect, and a blast-radius statement.

Never infer destructive consent from “clean up,” “reset,” or “fix it.”

## Enforce hard safety rules

### Protect credentials and masked values

- Never read or print `~/.openship/config.json`.
- Never echo PATs, bearer headers, environment values, database credentials, private keys, or secret files.
- Treat `••••••••` and `__OPENSHIP_MASKED__` as sentinels, not actual values.
- Preserve a masked secret unless the user explicitly replaces/deletes it through a safe input path.
- Do not write secrets into `openship.json`, source control, shell history, build args, logs, evidence files, or reports.
- List environment keys and safe metadata by default, never values.

### Review build configuration before triggering work

Inspect package scripts, Dockerfile/Containerfile, Compose, `openship.json`, task files, shell scripts, and CI workflows without returning matching source snippets.

Block high-confidence patterns including:

```text
printenv / complete env dump
set -x or shell xtrace
serialization of process.env or os.environ
cat .env
printing sensitive variables
credential-bearing URLs or inline private keys
sensitive Docker ARG/ENV or --build-arg use
```

Do not assume Docker build args are safe for secrets. Verify a supported ephemeral secret mechanism or use an out-of-band path.

### Read before PATCH

Fetch the complete resource before partial updates.

For Services, treat `environment` and `advanced` as merge-like only when live schema confirms it. Treat arrays such as `ports`, `volumes`, `dependsOn`, and `publicEndpoints` as whole-value replacements unless live schema states otherwise. Build the complete desired array before PATCH.

Never “add one volume” by sending only the new volume to a replacement field.

### Protect stateful services

Before changing a database, queue, object store, or service with persistent volumes:

1. resolve exact service/project/context;
2. list image, command, environment key metadata, ports, volumes, dependencies, and health;
3. identify shared consumers;
4. check backup and restore procedure;
5. verify image/data/extension compatibility;
6. distinguish container recreation from volume deletion;
7. state rollback;
8. make the minimum change;
9. verify data and application behavior after recreation.

Never delete or replace a persistent volume to solve an image/extension problem.

### Treat restart and config application differently

Restart may bounce the current materialized container without applying new desired configuration. When config is stale, use the supported refresh/redeploy path for the selected service rather than repeatedly restarting it.

### Restrict exec

Use status, bounded sanitized logs, health, desired config, deployment state, and volume metadata before exec.

Exec is R3. Use one narrow non-interactive command only when explicitly requested or necessary after safer diagnostics. Never use `env`, `printenv`, `/proc/*/environ`, credential paths, or broad config dumps. Do not install packages or mutate data without separate authorization and rollback.

### Handle pending actions exactly

`pending` or `action_required` is not automatically failed. Read pending actions and use only server-provided action IDs and allowed resolutions. Never guess an action ID or destructive resolution.

## Work by domain

Load only the relevant reference before non-trivial work:

- Resource model and contexts: [references/model.md](references/model.md)
- Channel selection: [references/routing.md](references/routing.md)
- General risk and destructive policy: [references/safety.md](references/safety.md)
- Secret exposure, builds, env, and logs: [references/secrets.md](references/secrets.md)
- Projects, linking, env metadata, config: [references/projects.md](references/projects.md)
- Deployments and pending actions: [references/deployments.md](references/deployments.md)
- Services, Compose, volumes, databases: [references/services.md](references/services.md)
- Servers, backups, edge, mail: [references/infrastructure.md](references/infrastructure.md)
- API, MCP, permissions, schemas: [references/api-and-mcp.md](references/api-and-mcp.md)
- Failure diagnosis: [references/troubleshooting.md](references/troubleshooting.md)

## Verify every change

Choose evidence that proves the requested outcome without revealing values:

- project update: GET and compare intended fields;
- env update: confirm key/scope/masked metadata only;
- service update: GET desired state, inspect drift/stale status, and check health;
- deploy: follow to terminal state, inspect only bounded sanitized error context, and probe returned URLs when appropriate;
- domain: read route/certificate status;
- backup: read record and artifact status without credentials;
- restore/migration: verify service health and application data, not only job completion;
- instance repair/update: rerun `status` and `doctor`.

Do not report success while status remains `queued`, `building`, `pending`, `action_required`, `degraded`, or equivalent.

## Report a compact operational record

Return:

```text
Target: <context / instance / project / service>
Risk: <R0-R3>
Secret exposure: <decision and evidence scope, never values>
Observed: <relevant initial state>
Action: <channel and exact non-secret change>
Result: <terminal status and identifiers>
Verified by: <read-back, health, sanitized logs, or endpoint evidence>
Remaining risk: <none or explicit follow-up>
```

Do not dump raw JSON or full logs. Quote only the sanitized lines needed to establish the result.

## Stop conditions

Stop rather than improvise when:

- active context and project link disagree for a write;
- target identity is ambiguous;
- CLI/schema cannot confirm an option or body;
- remote secret presence is unknown before a sensitive operation;
- any relevant output sink is unknown or plaintext while secrets may be touched;
- a build configuration contains a high-confidence leak pattern;
- a mutation would replace unknown arrays or masked secrets;
- a stateful change cannot preserve data;
- a destructive action lacks explicit authorization;
- a safe write-only secret input path is unavailable;
- the platform returns an out-of-band authorization or user-decision flow;
- evidence suggests a platform defect rather than user configuration.

For suspected defects, preserve only version, sanitized command/tool name, non-secret arguments, resource IDs, status, error category, and bounded sanitized text.
