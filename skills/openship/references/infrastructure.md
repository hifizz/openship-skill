# Instance and infrastructure operations

## Contents

1. Distinguish local and remote instances
2. Instance lifecycle
3. Doctor and repair
4. Servers and host control
5. System and edge
6. Mail infrastructure
7. Backups and restore
8. Update, reset, and uninstall

## 1. Distinguish local and remote instances

Use preflight and `/health/env` to determine:

- active context and API URL;
- self-hosted versus cloud;
- local versus remote target;
- deploy/auth/team mode;
- local host/Docker capabilities;
- installed service manager and ports when local.

A self-hosted instance is not necessarily local to the agent. Local service-manager, filesystem, Docker, and repair operations only make sense on the machine hosting that instance.

Do not run local host commands merely because `selfHosted` is true.

## 2. Instance lifecycle

Use dedicated commands for local lifecycle:

```bash
openship up
openship stop
openship --json status
```

Inspect live help before passing install method, port, or service-manager options.

After start/restart:

- wait for API health;
- confirm resolved API/dashboard ports;
- confirm active context still targets the intended instance;
- run `status` again.

Do not edit generated Compose/service-manager files directly unless the dedicated command cannot represent the required repair and the user accepts configuration drift.

## 3. Doctor and repair

Use `openship doctor` as the first diagnostic for the local instance. It can distinguish local deep health from a remote lightweight preflight.

Prefer read-only/report mode first:

```bash
openship --json doctor
```

Use repair/fix only after inspecting:

- service state;
- API reachability;
- database health/corruption signal;
- recent service error;
- data directory;
- backup behavior;
- affected projects/services.

A repair that backs up and heals an embedded database is still R2/R3 depending on impact. Preserve the reported backup path and verify database/application health afterward.

Do not apply local repair against a remote context.

## 4. Servers and host control

Server operations can affect every project scheduled to that host.

Before create/update/remove:

- list servers and status;
- resolve the exact server ID;
- inspect projects/workloads assigned to it;
- inspect host-control connectivity;
- identify SSH/agent/network requirements;
- state maintenance and migration impact.

Use dedicated `openship server` commands or confirmed API routes. Do not bypass host-control by directly editing the host unless the platform's recovery instructions require it.

For removal, verify workload evacuation and persistent-data location first.

## 5. System and edge

System and edge resources may control routing, certificates, ports, Docker runtime, firewall, DNS, or shared components.

Treat changes as R2 or R3.

Before changing:

- check self-host capability;
- read current system/edge state;
- identify every affected project/domain;
- inspect pending actions;
- verify rollback or previous configuration;
- apply one change at a time;
- rerun health and endpoint checks.

Avoid a parallel manual change in Docker, firewall, reverse proxy, or DNS while an Openship operation is pending; it obscures the source of truth.

## 6. Mail infrastructure

Mail setup can be a guided UI flow rather than a single in-band API call.

When an install/API response returns `flowHref`:

1. show the URL or navigation instruction safely;
2. explain which authorization/configuration step remains;
3. do not claim installation is complete;
4. after completion, read mail/system/project state;
5. verify DNS, certificates, service health, and a non-sensitive connectivity/test result.

Protect SMTP credentials, DKIM keys, API tokens, and mailbox passwords.

## 7. Backups and restore

### Backup

Before creating/configuring a backup:

- identify project/service/storage scope;
- distinguish control-plane metadata from application data;
- inspect destination and encryption behavior;
- check retention and storage cost;
- verify a completed artifact, not only a queued job.

### Restore

Restore is R3. Before it:

1. resolve exact backup ID/artifact;
2. inspect creation time, source, version, and integrity status;
3. identify the destination and overwrite semantics;
4. stop or quiesce writers when required;
5. preserve the current state with a fresh backup when possible;
6. state data-loss window and dependency impact;
7. execute the supported restore/migration path;
8. verify runtime health and representative application data;
9. preserve operation IDs and logs.

Do not restore into a different major database/runtime version without a documented migration plan.

## 8. Update, reset, and uninstall

### Update

Before updating Openship itself:

- read current version and latest available version;
- inspect release notes relevant to storage, migrations, CLI/API compatibility, and deployment runtime;
- confirm backup state;
- check local disk and service health;
- plan rollback or recovery;
- run the dedicated update command;
- verify version, migrations, API, dashboard, and deployed workloads.

### Reset admin

Reset-admin is privileged R3. Confirm the exact local instance and account recovery goal. Never expose the resulting credential.

### Uninstall

Uninstall is R3. Determine whether it removes:

- service-manager units;
- Compose containers;
- embedded database/control-plane data;
- deployed workloads;
- persistent volumes;
- CLI configuration.

Obtain explicit authorization for each persistent-data effect. Verify what remains after uninstall.
