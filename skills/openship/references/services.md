# Services, Compose, volumes, and databases

## Contents

1. Inspect a service
2. Create and update
3. Replacement versus merge semantics
4. Start, stop, restart, and refresh
5. Compose sync and drift
6. Volumes and stateful data
7. PostgreSQL and pgvector changes
8. Runtime logs and exec
9. Delete safely

## 1. Inspect a service

Resolve the project first, then the service:

```bash
openship --json service list --project proj_xxx
openship --json service get svc_xxx --project proj_xxx
```

Use live help for exact ordering/options.

Collect:

- service ID and name;
- kind/source;
- image or build context;
- Dockerfile and command;
- enabled/exposed state;
- ports and public endpoints;
- environment key metadata;
- dependencies;
- restart policy;
- volumes/mounts;
- advanced namespace/network settings;
- drift and stale-config state;
- running container/runtime status.

Do not infer the running container's config solely from desired service config.

## 2. Create and update

For create, choose exactly one source strategy supported by the current schema:

- image;
- build context/Dockerfile;
- imported/synced Compose service;
- detected monorepo sub-application.

Use explicit ports and exposure only when required. Avoid publishing databases publicly by default.

For update:

1. GET the full service;
2. get the live input schema/help;
3. build a minimal patch while preserving replacement fields;
4. send the patch;
5. GET the service again;
6. apply via refresh/redeploy when required;
7. verify runtime health.

## 3. Replacement versus merge semantics

Current Openship service semantics distinguish merge-like fields from whole-value replacements. Confirm them live, then follow this conservative default:

### Merge-like

- `environment` object;
- `advanced` object.

Omitted keys remain. A key set to `null` may remove it when the live schema confirms that behavior. A whole field set to `null` may clear it.

### Whole-value replacement

- `ports`;
- `volumes`;
- `dependsOn`;
- `publicEndpoints`;
- other list-valued fields.

To append one port or volume:

```text
GET current list
+ apply requested addition locally
+ validate duplicates/conflicts
+ PATCH the complete resulting list
```

Never send only the new element to a replacement field.

Masked environment values are sentinels. Echo a supported sentinel only when the schema explicitly defines that as “keep unchanged”; otherwise omit the key.

## 4. Start, stop, restart, and refresh

Use container actions for runtime lifecycle only:

- start: start a stopped materialized service;
- stop: stop it;
- restart: bounce it;
- refresh/redeploy: recreate/apply desired configuration.

A restart does not necessarily apply new env/config because a container's environment is fixed at creation. When the API returns a stale-config conflict, read the named drifted keys and use a refresh deployment scoped to that service.

Do not force restart past a stale-config warning unless the user explicitly wants a bounce of the old config.

## 5. Compose sync and drift

Compose is both source configuration and a control-plane import/sync source. Before sync:

- run `docker compose config` only on trusted repository content;
- inspect normalized services, ports, mounts, dependencies, commands, and build contexts;
- identify unsupported namespaces/mount features;
- preserve read-only mount flags and host IP bindings;
- distinguish named volumes from bind mounts;
- identify stateful services that should not be recreated unnecessarily.

After sync, inspect each service's drift state.

For drift resolution:

- **accept upstream** when the Compose definition should become desired state;
- **keep local edits** when Openship's current override should remain.

Do not choose globally without reviewing service-by-service impact.

## 6. Volumes and stateful data

For every mount, classify:

- named volume;
- host bind mount;
- read-only bind;
- ephemeral/tmpfs;
- external storage.

Record source, target, read-only state, ownership, and sharing.

Before image or command changes, verify the new process expects the same mount path and data format.

Container deletion/recreation and volume deletion are separate decisions. Preserve volumes by default.

Use volume size/status reads when available. A large or actively changing volume increases backup and rollback requirements.

## 7. PostgreSQL and pgvector changes

Use this sequence for adding pgvector to an existing PostgreSQL service:

1. resolve the exact project/service and PostgreSQL major version;
2. inspect the current image digest/tag, data volume, mount path, health, and consumers;
3. create or verify a usable backup;
4. choose a pgvector-capable image compatible with the same PostgreSQL major version, or a supported package installation strategy;
5. confirm UID/GID, entrypoint, data directory, and extension files are compatible;
6. update only the image/config needed; preserve the volume list exactly;
7. refresh/redeploy the service rather than deleting it;
8. wait for PostgreSQL health;
9. run a narrow database check using a safe credential path;
10. create `vector` in each intended database only after the server exposes the extension;
11. verify application connections and representative data;
12. preserve the old image reference for rollback.

Do not:

- change the PostgreSQL major version in the same operation;
- initialize an empty data directory over the existing mount;
- delete the volume to resolve extension loading;
- install packages interactively in a running container as the permanent solution;
- assume `CREATE EXTENSION` in one database enables all databases.

For a shared PostgreSQL service, list every dependent project/service before change and schedule impact accordingly.

## 8. Runtime logs and exec

Use non-streaming logs for focused evidence and streaming only while actively observing a restart/deploy.

Classify log source:

- build logs;
- deployment orchestration logs;
- service runtime stdout/stderr;
- database/application logs inside a volume.

Container exec is R3. Use it only after read-only surfaces are insufficient.

Safe diagnostic examples are narrow and non-secret, such as checking a binary version or a known file's presence. Avoid broad shell enumeration.

## 9. Delete safely

Before deleting a service:

- GET it;
- list volumes and dependencies;
- determine whether the API deletes only the service/container or storage too;
- verify no domain/public endpoint still depends on it;
- obtain explicit authorization for persistent-data effects;
- delete by service ID;
- verify control-plane and runtime cleanup.

Do not delete a service to apply an image update when refresh/redeploy is available.
