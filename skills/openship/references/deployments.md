# Deployments, logs, pending actions, and verification

## Contents

1. Choose the deployment path
2. Git deployment
3. Folder deployment
4. Watch and classify status
5. Handle pending actions
6. Diagnose failures
7. Refresh and redeploy
8. Verify and report

## 1. Choose the deployment path

Use the current repository state:

- inside a Git repository with a linked project: Git deployment is normally appropriate;
- outside Git or for an explicit local folder upload: use the folder deployment flow;
- prebuilt image/release source: use the current project release-image or service image flow;
- Compose stack: preserve service scoping and stateful services.

Inspect:

```bash
openship deploy --help
openship deployment --help
openship logs --help
```

Resolve the project and target environment before triggering work.

## 2. Git deployment

Before deploying:

1. identify active context and linked project;
2. inspect repository root, branch, HEAD SHA, and working-tree changes;
3. determine whether the user wants the current branch, a remote branch, or an exact commit;
4. verify project source linkage and branch settings;
5. validate `openship.json` if present;
6. identify affected services for a monorepo/stack;
7. decide production versus preview explicitly.

Prefer an exact commit for production-critical work when reproducibility matters.

A dirty working tree is not automatically part of a Git deployment. State that uncommitted files will not be included unless the chosen folder-upload flow packages them.

Trigger the narrowest supported deployment. Use `--watch` or the current equivalent when the user expects completion in the same operation.

## 3. Folder deployment

A folder deployment packages local files and may include uncommitted changes. Before it:

- verify the exact directory;
- inspect ignore rules and large/sensitive files;
- exclude `.git`, local credentials, caches, databases, build artifacts, and unrelated parent directories;
- validate the detected stack and configuration diagnostics;
- resolve whether this creates a project or updates an existing project.

Prefer the dedicated `openship deploy` folder path because it handles session creation, archive upload, scan, project ensure, and deployment orchestration.

If an MCP prompt exposes the lower-level flow, remember that the raw archive upload is out of band; do not put binary content in JSON-RPC.

## 4. Watch and classify status

Capture the deployment ID immediately.

Classify the returned state:

- progress: queued/preparing/building/deploying;
- success: ready/succeeded/current equivalent;
- failure: failed/error;
- cancellation: cancelled;
- blocked: pending/action_required.

Poll or stream with bounded waits. Do not create duplicate deployments merely because one is still building.

Use deployment logs for build activity and service runtime logs for post-start crashes. Keep those evidence sources distinct.

## 5. Handle pending actions

When a deployment is pending or `action_required`:

1. GET the deployment;
2. GET its pending actions or the project's pending-action collection;
3. show each action's reason, expiry, and server-provided allowed resolutions;
4. use only the returned action ID and resolution payload;
5. obtain user input when the choice changes ports, resources, routing, or data behavior;
6. submit the response;
7. resume monitoring.

Do not:

- mark pending as failed;
- guess an action ID;
- retry the whole deployment before resolving or allowing the pending action to expire;
- choose a destructive resolution without explicit authorization.

## 6. Diagnose failures

Collect this minimal evidence bundle:

```text
context and instance
CLI/server version
project ID
deployment ID
branch and commit
terminal status
error code/message
last relevant build-log section
service/runtime status and last relevant runtime-log section
config diagnostics
pending actions, if any
```

Classify failure stage:

- source access/checkout;
- detection/config validation;
- dependency installation;
- build;
- image creation/pull;
- container/runtime creation;
- port/routing/certificate;
- health check;
- application runtime.

Fix the cause, not the last visible symptom. For example, a runtime restart cannot repair a failed build.

Avoid dumping complete logs. Preserve enough surrounding lines to show the first causal error and its context.

## 7. Refresh and redeploy

Distinguish operations:

- restart: bounce the currently materialized service;
- refresh: reapply current desired env/config without a source rebuild when supported;
- redeploy: materialize a source/image version again;
- rebuild: rerun build steps;
- rollback: restore a prior deployment snapshot/version.

When service config is stale, use the live supported refresh/redeploy route for the selected service. Repeated restart may continue running old environment/config.

Before rollback:

- inspect the selected prior deployment;
- understand whether data migrations are backward-compatible;
- preserve current deployment ID and state;
- verify the restored version and public endpoint afterward.

## 8. Verify and report

A deployment is complete only when:

- it reaches a terminal success state;
- required services are healthy;
- expected URLs are present;
- no unresolved pending actions remain;
- config diagnostics do not show ignored critical settings;
- an endpoint probe or application-level read confirms the expected version when appropriate.

Report:

```text
Project / context:
Environment:
Source branch / commit or folder:
Deployment ID:
Terminal state:
Services affected:
URLs:
Verification evidence:
Warnings / rollback:
```
