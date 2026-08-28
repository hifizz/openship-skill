# Projects, repository links, configuration, and environment

## Contents

1. Inspect and resolve a project
2. Link a repository
3. Create or update a project
4. Handle `openship.json`
5. Manage environment variables safely
6. Link source control
7. Domains and public endpoints
8. Delete safely

## 1. Inspect and resolve a project

Start with:

```bash
openship --json project list
openship --json project get proj_xxx
```

Use current help when command shape differs:

```bash
openship project --help
openship project get --help
```

Resolve by ID whenever possible. If the user supplies a name/slug, list projects and require a unique exact match.

Inspect at least:

- `id`, `name`, `slug`, and status;
- source type and repository linkage;
- branch and auto-deploy settings;
- framework/build/runtime fields;
- Services and domains when relevant;
- current/latest deployment.

## 2. Link a repository

`openship init` creates `.openship/project.json` for the current/selected directory.

Before linking:

1. run preflight;
2. confirm repository root;
3. list projects in the selected context;
4. choose exact project ID;
5. select default environment deliberately.

Inspect live help and use a non-ambiguous form, for example:

```bash
openship init --project proj_xxx --environment production
```

After linking:

- read `.openship/project.json` through the allowlisted preflight helper;
- verify `projectId` and stored `context`;
- rerun preflight;
- commit the link file only when the team intends the repository to target that shared project/context.

Do not overwrite an existing link with `--force` until old and new targets have been shown.

## 3. Create or update a project

Use a dedicated project command when available. Before create, determine:

- source: Git, folder upload, image, or Service stack;
- project type;
- desired slug/domain;
- framework/build/runtime settings;
- container port;
- target environment;
- whether auto-deploy is wanted.

Keep initial payload minimal. Let detection provide defaults unless an override is necessary.

Before update:

1. GET project;
2. read current route/schema;
3. classify changed-field semantics;
4. run the Secret Exposure Gate when build/env/output can be affected;
5. send only supported fields;
6. GET project again.

A project-row change does not necessarily prove runtime reconfiguration; some changes require refresh/deploy.

## 4. Handle `openship.json`

`openship.json` is an authoritative overlay applied after source detection. Keep it small.

Workflow:

1. inspect `package.json`, lockfiles, framework config, Dockerfiles, Compose, and monorepo metadata;
2. determine what detection should infer;
3. add only fields that need pinning/override;
4. include current schema URL when supported;
5. scan config for Secret Exposure Gate findings;
6. validate with installed CLI;
7. deploy only after output sinks are classified;
8. verify resulting config.

Use live commands:

```bash
openship config --help
openship config validate
```

Do not assume JSONC support. Avoid comments/trailing commas unless current validation allows them.

Never store real secret values, credential URLs, private keys, or secret build args in `openship.json`.

When a separate official/current `openship-config` skill is available, use it for repository analysis/config authoring, then return here for safety gate, validation, deployment, and verification.

## 5. Manage environment variables safely

Environment operations are secret-sensitive even when nominally read-only.

### Inspect metadata, not values

First inspect live help and choose an endpoint/command proven to return key metadata only:

```bash
openship project env --help
```

Safe output includes:

```text
key name
environment/scope
isSecret or masked status
updatedAt
```

Do not call an endpoint/tool until its response behavior is classified by schema/current source or disposable-canary evidence. Do not retrieve plaintext merely to preserve or compare it.

Run:

```bash
python3 scripts/secret_exposure_preflight.py \
  --operation env-read \
  --remote-env-state present \
  --evidence-file /secure/path/evidence.json \
  --fail-closed
```

### Set non-sensitive values

Before a non-sensitive write:

- resolve project and environment;
- read key metadata only;
- preserve unspecified keys and masked sentinels;
- use the narrowest key-level set/merge operation;
- confirm whether refresh/redeploy is required;
- keep command/API output bounded and sanitized.

Do not send the complete environment object when a single-key operation exists.

### Set secret values

The Agent should manage key name, scope, and lifecycle, not plaintext.

Preferred flow:

```text
Agent resolves project/environment/key
→ platform opens interactive or write-only value entry
→ user supplies value outside Agent transcript
→ Agent verifies key metadata/masked state
→ refresh/redeploy only after Build/Log sinks pass the gate
```

Do not place a secret in:

```text
chat text
displayed command or --data JSON
shell history/process arguments
openship.json / Compose / Docker build args
source control
operation journal/evidence file
logs or final report
```

If no write-only/interactive mechanism is proven, return `require-out-of-band-entry` and direct the user to the safe Dashboard flow.

### Apply and verify

After a write, verify without echoing the value:

- key exists;
- correct project/environment/scope;
- secret/masked metadata is correct;
- update timestamp changed when available;
- refresh/deploy reached terminal success;
- application health/behavior confirms the change without printing the credential.

See [secrets.md](secrets.md).

## 6. Link source control

Before linking GitHub:

1. confirm GitHub is connected for current Openship organization;
2. resolve owner/repository/branch;
3. detect stack/build config when supported;
4. verify current token has metadata/deploy access;
5. avoid requesting repository content unless genuinely required.

After linking, GET project and verify owner/name/branch and auto-deploy settings.

Repository permission may allow metadata/deployment without file-content access. Missing file-read tools do not automatically mean the GitHub connection is broken.

## 7. Domains and public endpoints

Treat free subdomains, custom domains, certificates, routing, and Service public endpoints as related but distinct resources.

Before adding a domain:

- resolve project/Service;
- determine container port/public endpoint;
- check conflicting hostname;
- understand DNS records for custom domains.

After adding:

- read domain state;
- read certificate/routing state;
- verify public URL;
- do not report success while certificate/routing remains pending.

## 8. Delete safely

Project deletion is R3 because it can tear down Services, deployments, domains, and persistent storage.

Before delete:

1. GET project;
2. list Services, volumes, domains, and recent backups;
3. determine force/orphan/volume-wipe semantics from live help;
4. state exact data impact;
5. obtain explicit authorization for volume deletion;
6. execute by project ID;
7. verify removal or intentional orphaning.

Do not use deletion as a shortcut for deployment/configuration repair.
