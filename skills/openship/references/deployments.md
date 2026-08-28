# Deployments, builds, logs, pending actions, and verification

## Contents

1. Choose the deployment path
2. Secret exposure before build/deploy
3. Git deployment
4. Folder deployment
5. Watch and classify status
6. Handle pending actions
7. Diagnose failures safely
8. Refresh and redeploy
9. Verify and report

## 1. Choose the deployment path

Use current repository state:

- inside a Git repository with a linked project: Git deployment is normally appropriate;
- outside Git or for an explicit local-folder upload: use folder deployment;
- prebuilt image/release source: use current release-image or Service image flow;
- Compose stack: preserve Service scoping, environment semantics, and stateful Services.

Inspect live help:

```bash
openship deploy --help
openship deployment --help
openship logs --help
```

Resolve project, target environment, branch/commit, and production/preview intent before triggering work.

## 2. Secret exposure before build/deploy

No build or deploy starts until the Secret Exposure Gate returns `allow` or `allow-with-redaction`.

First classify the selected remote environment without retrieving values:

```text
none: no sensitive variables verified
present: sensitive variables exist; key/secret metadata only
unknown: not established; blocking
```

Then run:

```bash
python3 scripts/secret_exposure_preflight.py \
  --cwd "$PWD" \
  --operation deploy \
  --remote-env-state present \
  --evidence-file /secure/path/evidence.json \
  --fail-closed
```

Review package scripts, Dockerfile/Containerfile, Compose, `openship.json`, task files, shell scripts, and CI workflows. Block complete environment dumps, shell xtrace, process-environment serialization, `.env` output, sensitive-variable echoing, credential URLs, inline private keys, and unverified sensitive Docker build arguments.

Build logs are potentially persistent and externally collected. A sanitizer on local display does not prove the stored log is safe. Use current schema/source or a disposable fake-canary test to classify build-log, Docker-history, API/MCP-response, and artifact behavior.

See [secrets.md](secrets.md).

## 3. Git deployment

Before deploying:

1. identify active context and linked project;
2. inspect repository root, branch, HEAD SHA, and working-tree changes;
3. determine current branch, remote branch, or exact commit;
4. verify project source linkage and branch settings;
5. validate `openship.json` if present;
6. identify affected Services for a monorepo/stack;
7. decide production versus preview;
8. pass the Secret Exposure Gate.

Prefer an exact commit for production-critical work.

A dirty working tree is not automatically part of a Git deployment. State that uncommitted files will not be included unless a folder-upload path packages them.

Trigger the narrowest supported deployment. Use `--watch` or current equivalent when completion is expected in the same operation.

## 4. Folder deployment

A folder deployment packages local files and may include uncommitted changes. Before it:

- verify the exact directory;
- inspect ignore rules and sensitive-file names;
- exclude `.git`, `.env*`, private keys, credential files, caches, databases, build artifacts, and unrelated parent directories;
- validate detected stack/config diagnostics;
- resolve whether this creates or updates a project;
- run the Secret Exposure Gate for the packaged scope.

Prefer dedicated `openship deploy` folder flow because it handles session creation, archive upload, scan, project ensure, and deployment orchestration.

If an MCP prompt exposes lower-level flow, raw archive upload remains out of band; do not put binary content in JSON-RPC.

## 5. Watch and classify status

Capture the deployment ID immediately.

Classify state:

- progress: queued/preparing/building/deploying;
- success: ready/succeeded/current equivalent;
- failure: failed/error;
- cancellation: cancelled;
- blocked: pending/action_required.

Poll/stream with bounded waits. Do not create duplicates merely because one is still building.

Use deployment logs for build activity and Service runtime logs for post-start crashes. Keep evidence sources distinct and classify each output sink before reading it.

Do not stream complete logs into Agent context.

## 6. Handle pending actions

When a deployment is pending or `action_required`:

1. GET the deployment;
2. GET pending actions;
3. show each action's non-secret reason, expiry, and server-provided allowed resolutions;
4. use only returned action ID and resolution payload;
5. obtain user input when choice changes ports, resources, routing, secret handling, or data behavior;
6. submit response;
7. resume monitoring.

Do not mark pending as failed, guess an action, redeploy before resolving it, or select a destructive resolution without explicit authorization.

## 7. Diagnose failures safely

Collect the minimum metadata bundle:

```text
context and instance
CLI/server version
project ID
deployment ID
branch and commit
terminal status
error code/category
config diagnostics
pending-action metadata
```

Before retrieving text logs, classify output behavior and request the narrowest range. Pipe selected content through:

```bash
python3 scripts/log_leak_scan.py /tmp/selected-log.txt --fail-on-detection
```

Never dump complete build/runtime logs or full environment/config objects.

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

Fix the cause, not the last symptom. A runtime restart cannot repair a failed build.

If a canary or probable credential is detected, stop output, identify the sink without repeating the value, contain access, and advise rotation when real credentials may be affected.

## 8. Refresh and redeploy

Distinguish:

- restart: bounce currently materialized Service;
- refresh: reapply desired env/config without source rebuild when supported;
- redeploy: materialize source/image again;
- rebuild: rerun build steps and therefore rerun the Secret Exposure Gate;
- rollback: restore a prior deployment snapshot/version.

When Service config is stale, use supported refresh/redeploy for the selected Service. Repeated restart may continue running old config.

Before rollback, inspect prior deployment, data-migration compatibility, current deployment ID/state, and any secret-output changes between versions. Verify restored version and public endpoint afterward.

## 9. Verify and report

A deployment is complete only when:

- terminal success state reached;
- required Services healthy;
- expected URLs present;
- no pending actions remain;
- config diagnostics have no ignored critical settings;
- endpoint/application-level read confirms expected version when appropriate;
- displayed evidence contains no detected credential patterns.

Report:

```text
Project / context:
Environment:
Source branch / commit or folder:
Secret exposure decision / evidence scope:
Deployment ID:
Terminal state:
Services affected:
URLs:
Verification evidence:
Warnings / rollback:
```

Never include environment values, canary values, raw credentials, or unsanitized logs.
