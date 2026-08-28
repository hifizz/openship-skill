# Safety policy

## Contents

1. Risk levels
2. Context guard
3. Resource identity
4. Secret policy
5. Update semantics
6. Stateful workloads
7. Destructive operations
8. Exec and host commands
9. Verification and audit record

## 1. Risk levels

### R0 — Read-only

Examples:

- status, health, capabilities;
- list/get project, service, deployment, domain, server, backup;
- logs and non-secret configuration inspection;
- MCP `tools/list` and `prompts/list`.

Execute directly. Avoid revealing unnecessary internal or personal data.

### R1 — Routine reversible

Examples:

- deploy an explicit branch or commit;
- link a repository;
- add a normal domain;
- update a non-sensitive scalar setting;
- restart a known stateless service.

Require an unambiguous target and explicit desired result. Verify after execution.

### R2 — Stateful or infrastructure

Examples:

- change image, command, ports, network, volumes, or dependency graph;
- modify a database service;
- Compose sync or drift resolution;
- server, edge, mail, backup scheduling, or routing changes.

Read current state, dependencies, persistence, backup, and rollback first. Present the plan before execution.

### R3 — Destructive or privileged

Examples:

- delete a project/service/domain/server/backup;
- wipe volumes;
- restore or migrate data;
- reset admin or uninstall;
- arbitrary container exec;
- host-level shell or firewall command.

Require the exact target, explicit authorization for the destructive effect, and a blast-radius statement. A general request to “fix,” “reset,” or “clean up” is not sufficient consent.

## 2. Context guard

Before any write, compare:

```text
active CLI context
active API URL
project-link context
project ID
repository root
```

Block the write when the link context and active context differ.

Do not silently switch contexts because context switching changes the destination of every authenticated command. Show the available contexts without tokens, let the user-selected destination drive the switch, then rerun preflight.

A missing project link is not always blocking: an explicit project ID can be sufficient. A stale or conflicting link is blocking until resolved.

## 3. Resource identity

Use IDs for R2/R3 and preferably for all writes.

Never:

- choose the first list result;
- fuzzy-match a destructive target;
- assume service names are globally unique;
- infer a project from a Git repository name alone;
- reuse an ID returned by a different context.

For deletes, repeat the resolved identity and persistence effect immediately before execution.

## 4. Secret policy

Never access or emit:

- `~/.openship/config.json` contents;
- PATs or OAuth access tokens;
- bearer headers;
- secret environment values;
- database passwords, private keys, SMTP credentials, or cloud secrets.

Use only safe metadata such as `hasToken`, key name, `isSecret`, and masked status.

Treat these as sentinels:

```text
••••••••
__OPENSHIP_MASKED__
```

Do not:

- save them as literal replacement values;
- infer the secret is empty;
- overwrite the secret with `null` or `""` unless deletion is explicitly requested;
- include a user-supplied secret in a command shown back to the user.

When a secret must be set, prefer a mechanism that accepts it without persisting it in shell history. If no safe mechanism is available, stop and explain the secure input step.

## 5. Update semantics

Always GET before PATCH/PUT.

Classify fields as one of:

- scalar replacement;
- object merge;
- full object replacement;
- full array replacement;
- secret sentinel-preserving;
- action endpoint with no persistent config mutation.

For service updates, assume arrays replace wholesale unless the live schema says otherwise. Typical replacement fields include:

- `ports`;
- `volumes`;
- `dependsOn`;
- `publicEndpoints`;
- other list-valued runtime/build settings.

Construct the complete desired value from current state plus the requested change.

Do not send unknown fields “just in case.” Validation may reject them, or future versions may assign them meaning.

## 6. Stateful workloads

Treat a service as stateful if it has persistent volumes, stores durable data externally, or participates in replication/queues.

Before changing it, record:

```text
project ID
service ID
current image and tag
command/entrypoint
port mappings
volume names and mount paths
environment key names and secret flags
dependencies
health/status
latest usable backup
shared consumers
```

Then answer:

- Does the new image read the existing data format?
- Does it require an in-place migration?
- Is downgrade supported?
- Does the service need maintenance mode or traffic drain?
- Can the old container be recreated without touching volumes?
- How will success be checked at the data/application layer?

For PostgreSQL extensions such as pgvector, prefer an image or package strategy compatible with the existing major version and data directory. Do not replace or initialize the data directory. Verify the extension can be created in each required database after the service is healthy.

## 7. Destructive operations

Before delete, wipe, restore, migration, reset, or uninstall, state:

```text
Exact resource:
Context / instance:
Persistent data affected:
Dependent services or domains:
Backup / rollback:
Irreversible effect:
```

Use the platform's own confirmation/force flags only after this guard. Do not bypass a confirmation by calling a lower-level API with equivalent destructive effect.

`force` and `force-orphan` change semantics. Inspect live help and explain which resources may remain or be removed.

Never combine a routine config fix with volume deletion unless the user explicitly chooses data destruction after seeing alternatives.

## 8. Exec and host commands

Container exec and host-level commands are R3.

Prefer:

1. deployment status;
2. build/runtime logs;
3. health endpoints;
4. service desired config;
5. container metadata;
6. volume size/status;
7. only then exec.

For exec:

- run one narrow command;
- use a short timeout;
- avoid interactive shells;
- avoid `env`, `/proc/*/environ`, credential paths, and shell history;
- avoid package installation as an untracked permanent fix;
- avoid mutation unless separately authorized;
- capture exit code and minimal output.

For host commands, prefer dedicated `openship system`, `server`, `edge`, or `doctor` behavior. Manual Docker/firewall/systemd changes can drift from the control plane.

## 9. Verification and audit record

After a mutation, record:

- command channel used;
- sanitized arguments or body;
- target IDs;
- initial state relevant to the change;
- returned operation/deployment ID;
- terminal status;
- read-back fields;
- health/log/endpoint evidence;
- rollback availability;
- unresolved warnings.

Do not include tokens or secret values in the record.
