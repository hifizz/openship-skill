# Troubleshooting playbook

## Contents

1. Evidence-first triage
2. CLI or instance unavailable
3. Context and project-link problems
4. Authentication and permissions
5. Deployment stuck or failed
6. Service unhealthy or stale
7. Domain and routing problems
8. Stateful service and volume problems
9. Platform defect escalation

## 1. Evidence-first triage

Start with:

```bash
python3 scripts/preflight.py --cwd "$PWD"
openship --json status
```

Then collect only the domain-specific evidence needed.

Use this diagnosis order:

```text
wrong target/context
→ CLI/API availability
→ authentication/permission
→ desired configuration
→ deployment/build state
→ runtime/service health
→ routing/domain
→ persistent data
→ platform defect
```

Avoid changing multiple layers at once.

## 2. CLI or instance unavailable

### CLI missing

Evidence:

- `preflight.cli.installed` is false;
- `command -v openship` fails.

Action:

- stop operational execution;
- install/update through the official distribution path selected by the user;
- rerun version and preflight.

Do not substitute a random globally installed source checkout.

### API unreachable

Check:

- active context API URL;
- local service state and resolved ports;
- `openship status` diagnostics;
- local `openship doctor` when applicable;
- network/DNS/TLS for remote instances.

A stopped local instance can make API writes impossible but still allows local `up`/doctor actions.

Do not change context merely to find a reachable instance unless that instance is the intended target.

## 3. Context and project-link problems

### Context mismatch

Evidence:

```text
projectLink.context != instance.activeContext
```

Action:

1. stop writes;
2. show link path, project ID, active context, and API URL;
3. list safe context metadata;
4. switch only to the user-selected destination;
5. rerun preflight;
6. verify the project ID exists in that context.

### No project link

Options:

- use an explicit project ID for the current operation;
- run `openship init` after listing and selecting the target project;
- create a project first when none exists.

Do not initialize against the first project returned.

### Ambiguous project/service name

List exact matches and IDs. Require selection. Do not fuzzy-resolve a write.

## 4. Authentication and permissions

### Not logged in / invalid token

Use safe context/status output to confirm credential presence without reading it.

Run the current `openship login --help` and complete the supported login/PAT flow. Never ask the user to paste a long-lived PAT into chat or source code.

### 403 or hidden tools

Determine:

- current organization;
- role/read-only state;
- project/server/repository grant scope;
- whether the route is org-wide;
- whether GitHub content access is separately required.

A missing MCP tool may be intentional. Try a dedicated CLI or permitted resource-specific route before requesting broader grants.

### 404 for a known resource

Check context first. Then distinguish true absence from permission-hiding behavior. Never reuse an ID from another instance.

## 5. Deployment stuck or failed

### Still progressing

Read status and timestamps. Continue bounded monitoring rather than launching duplicates.

### Pending / action_required

Read pending actions and their expiry/allowed resolutions. Surface the exact choice. Use only server-provided action IDs.

### Build failure

Find the first causal error in:

- checkout/source access;
- config validation/detection;
- install;
- build;
- image creation.

Fix repository/config and redeploy. Restarting a runtime service cannot repair a failed build.

### Deploy/runtime failure

Inspect:

- image pull/start error;
- port conflict;
- volume mount/permission;
- health check;
- runtime logs;
- routing/certificate.

Do not force-delete volumes during runtime diagnosis.

## 6. Service unhealthy or stale

### Container stopped/crashing

Read service desired config, deployment result, and runtime logs. Check image/command/port/env/volume compatibility.

### Config stale conflict

A restart may preserve old env/config. Read the drifted keys, then use a service-scoped refresh/redeploy. Verify the recreated runtime reflects desired state.

### Compose drift

Review upstream versus local desired values per service. Choose accept/keep intentionally; do not mass-resolve stateful services blindly.

### Exec appears necessary

Confirm read-only surfaces cannot answer the question. Run one narrow, non-secret diagnostic command with a timeout. Treat any mutation as a separate R3 authorization.

## 7. Domain and routing problems

Inspect separately:

- domain record/resource;
- expected DNS records;
- certificate state;
- router/edge state;
- service public endpoint and container port;
- application health behind the route.

A healthy container does not prove DNS/TLS routing; a valid certificate does not prove the application is healthy.

Wait for genuinely asynchronous DNS/certificate states only when the platform indicates progress. Do not repeatedly recreate the domain.

## 8. Stateful service and volume problems

Before any attempted fix, capture:

- image and major version;
- volume name/source/target;
- data directory;
- ownership/permissions;
- backup status;
- dependent services;
- relevant logs.

Prefer reversible fixes:

- correct compatible image;
- correct mount path/permissions;
- refresh/recreate container while preserving volume;
- documented database recovery/migration.

Do not initialize, wipe, or replace a volume without explicit data-loss authorization.

## 9. Platform defect escalation

Suspect a platform defect when:

- a valid documented route returns an unexpected 500;
- MCP schema and route validation disagree;
- the CLI sends a supported operation but server behavior contradicts current source/docs;
- a deployment fails due to an Openship component rather than user source/config;
- control-plane state and runtime state cannot reconcile through supported actions.

Prepare a sanitized issue bundle:

```text
Openship CLI version
server/release version
self-host/cloud mode
OS/runtime details when relevant
command or MCP tool name
sanitized arguments/body
context label (not token)
project/service/deployment IDs
exact error code/message
minimal relevant logs
reproduction steps
expected versus actual behavior
```

Remove tokens, secret values, private repository content, internal hostnames when unnecessary, and personal data.
