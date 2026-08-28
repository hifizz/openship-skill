# Projects, repository links, configuration, and environment

## Contents

1. Inspect and resolve a project
2. Link a repository
3. Create or update a project
4. Handle `openship.json`
5. Manage environment variables
6. Link source control
7. Domains and public endpoints
8. Delete safely

## 1. Inspect and resolve a project

Start with:

```bash
openship --json project list
openship --json project get proj_xxx
```

Use current help when the command shape differs:

```bash
openship project --help
openship project get --help
```

Resolve a project by ID whenever possible. If the user supplies a name or slug, list projects and require a unique exact match.

Inspect at least:

- `id`, `name`, `slug`, and status;
- source type and repository linkage;
- branch and auto-deploy settings;
- framework/build/runtime fields;
- services and domains when relevant;
- current and latest deployment.

## 2. Link a repository

`openship init` creates `.openship/project.json` for the current or selected directory.

Before linking:

1. run preflight;
2. confirm the repository root;
3. list the target context's projects;
4. choose the exact project ID;
5. select the default environment deliberately.

Then inspect live help and run the non-ambiguous form, for example:

```bash
openship init --project proj_xxx --environment production
```

After linking:

- read `.openship/project.json` without exposing unrelated files;
- verify `projectId` and stored `context`;
- rerun preflight;
- add the link file to source control only when the team intends the repository to target that shared project/context.

Do not overwrite an existing link with `--force` until the old and new targets have been shown.

## 3. Create or update a project

Use a dedicated project command when available. Before create, determine:

- source: Git, folder upload, image, or service stack;
- project type;
- desired slug/domain;
- framework/build/runtime settings;
- container port;
- target environment;
- whether auto-deploy is wanted.

Keep the initial payload minimal. Let detection provide defaults unless the repository needs an override.

Before update:

1. GET the project;
2. read the current route/schema;
3. classify each changed field's semantics;
4. send only supported fields;
5. GET the project again.

Do not assume the project row alone proves the runtime was reconfigured. Some changes require a deploy or refresh.

## 4. Handle `openship.json`

`openship.json` is an authoritative overlay applied after Openship's source detection. Keep it small.

Workflow:

1. inspect `package.json`, lockfiles, framework config, Dockerfiles, Compose files, and monorepo metadata;
2. determine what detection should already infer;
3. add only fields that need to be pinned or overridden;
4. include the current schema URL when supported;
5. validate with the installed CLI;
6. deploy and verify the resulting detected/applied configuration.

Use live commands:

```bash
openship config --help
openship config validate
```

Do not assume JSONC support. Avoid comments and trailing commas unless current validation explicitly allows them.

Never store real secret values in `openship.json`. Use secret-aware control-plane environment handling.

When a separate official/current `openship-config` skill is available, use it for repository analysis and config authoring, then return to this operator workflow for validation, deployment, and verification.

## 5. Manage environment variables

First inspect key metadata without revealing secret values:

```bash
openship project env --help
openship --json project env get proj_xxx
```

Use the current CLI's merge/set behavior. Before a write:

- select the environment (`production`, `preview`, or current supported values);
- preserve all unspecified keys;
- preserve masked secret sentinels;
- distinguish project-level and service-level environment;
- identify whether applying the change requires a refresh deployment.

After a write, verify:

- key names;
- environment scope;
- secret flags;
- updated timestamps when available;
- deployment/runtime state if the value must be active immediately.

Do not print the supplied value in the final report.

## 6. Link source control

Before linking a GitHub repository:

1. confirm GitHub is connected for the current Openship organization;
2. resolve owner, repository, and branch;
3. detect the stack/build configuration when supported;
4. verify the current token has metadata/deploy access;
5. avoid requesting repository content access unless source inspection is genuinely required.

After linking, GET the project and verify repository owner/name/branch and auto-deploy settings.

A repository permission may allow metadata and deployment without file-content access. Do not interpret missing file-read tools as a broken GitHub connection.

## 7. Domains and public endpoints

Treat free subdomains, custom domains, certificates, routing, and service public endpoints as related but distinct resources.

Before adding a domain:

- resolve the project/service;
- determine the container port or public endpoint;
- check for an existing conflicting hostname;
- understand required DNS records for custom domains.

After adding:

- read domain state;
- read certificate/routing state;
- verify the resolved public URL;
- do not report success while certificate or routing remains pending.

## 8. Delete safely

Project deletion is R3 because it can tear down services, deployments, domains, and persistent storage.

Before delete:

1. GET the project;
2. list services, volumes, domains, and recent backups;
3. determine `force`, orphan, and volume-wipe semantics from live help;
4. state exact data impact;
5. obtain explicit authorization for any volume deletion;
6. execute by project ID;
7. verify the row/resources are removed or intentionally orphaned.

Do not use deletion as a shortcut for fixing a deployment or configuration problem.
