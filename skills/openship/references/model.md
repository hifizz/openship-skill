# Openship operating model

## Contents

1. Resource hierarchy
2. Instance and context
3. Repository and project link
4. Project and service
5. Deployment state
6. Identity resolution
7. Source-of-truth rules

## 1. Resource hierarchy

Use this conceptual hierarchy:

```text
Openship instance / control plane
└── organization
    ├── project
    │   ├── service
    │   │   ├── environment variables
    │   │   ├── ports / endpoints
    │   │   ├── volumes
    │   │   └── running container or runtime unit
    │   ├── deployment
    │   ├── domain
    │   ├── pending action
    │   └── backup or storage metadata
    ├── server
    ├── edge / routing infrastructure
    ├── mail infrastructure
    └── audit and system resources
```

Some resources are project-rooted, while others are organization-wide or self-host-only. Never infer that a project-scoped credential can operate organization-wide infrastructure.

## 2. Instance and context

An **instance** is the Openship control plane being addressed. It may be:

- a local self-hosted instance;
- a remote self-hosted instance;
- Openship Cloud.

A CLI **context** stores an API endpoint, dashboard endpoint, credential presence, and cached capabilities. The active context determines where authenticated CLI and `openship api` commands are sent.

A context name such as `production` is only a local label. Verify its API URL and instance mode; do not infer safety from the name.

Capability checks matter because commands can be:

- available everywhere;
- self-host-only;
- local-machine-only;
- hidden by the caller's permissions;
- absent in an older CLI or server version.

## 3. Repository and project link

A source repository is not an Openship project. `openship init` links a directory to a project by writing `.openship/project.json`.

The link commonly carries:

- `projectId`;
- optional project name or slug;
- the context active when the link was created;
- a default deployment environment.

Commands may search upward from the current directory for the nearest link. This makes subdirectory operation convenient, but it also creates two hazards:

1. a nested repository or worktree may resolve a different link than expected;
2. the stored link context may differ from the CLI's currently active context.

Always show the resolved link path and compare contexts before a write.

`openship.json` is a deployment configuration overlay in the repository. It is not the project link and should never contain credentials.

## 4. Project and service

A **project** is the control-plane resource that owns source linkage, build/runtime configuration, deployments, domains, and services.

A **service** is a configured application or infrastructure component inside a project. It may be built from source or run from an image.

Do not conflate these objects:

- service configuration: desired image, command, env, ports, volumes, dependencies;
- running container/runtime unit: the currently materialized process;
- persistent volume: storage whose lifecycle can outlive the container;
- deployment: an attempt to materialize a desired version/configuration.

Restarting a container does not necessarily apply a newly changed desired configuration. Recreating a container does not necessarily delete its volume. Deleting a service may or may not delete volumes depending on the selected operation; inspect the live semantics.

## 5. Deployment state

Treat deployment state as a state machine, not a boolean:

```text
queued → preparing → building → deploying → ready
                     ↘ failed
                     ↘ cancelled
                     ↘ pending / action_required
```

Exact state names can change by version. Classify them into:

- non-terminal progress;
- terminal success;
- terminal failure/cancellation;
- blocked pending user/system action.

A pending action carries server-generated identifiers and allowed resolutions. Read it before responding. Do not guess how to continue.

A deployment can produce:

- build logs;
- runtime logs;
- public URLs;
- per-service results;
- pending actions;
- failure metadata.

Use the deployment ID as the primary diagnostic key.

## 6. Identity resolution

Prefer stable IDs:

```text
project:    proj_...
service:    svc_...
deployment: platform-generated deployment ID
server:     platform-generated server ID
```

Resolve mutations using this order:

1. explicit ID;
2. linked project ID;
3. unique exact slug;
4. unique exact name.

List and stop on ambiguity. Do not choose the first fuzzy match.

For services, resolve the project first, then resolve the service within that project. A service name is not globally unique.

## 7. Source-of-truth rules

Use live data over remembered examples:

1. installed CLI help/version;
2. connected instance response and capability discovery;
3. current official docs/source;
4. bundled reference.

Use desired configuration to understand intent, but use control-plane reads and runtime health to understand what is actually active.

For incident work, preserve these identities in every note:

```text
context
API URL or instance label
project ID
service ID when applicable
deployment ID when applicable
CLI version
server/platform version when available
```
