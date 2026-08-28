# Execution routing

## Contents

1. Routing matrix
2. Discovery sequence
3. Dedicated CLI
4. Authenticated REST
5. MCP discovery
6. UI and out-of-band steps
7. Fallback and failure rules

## 1. Routing matrix

| Need | Preferred channel | Reason |
|---|---|---|
| Local instance lifecycle | Dedicated CLI | Handles service manager, ports, local repair, and interaction |
| Repository link | Dedicated CLI | Writes and resolves `.openship/project.json` |
| Common project/service/domain action | Dedicated CLI | Stable UX and built-in checks |
| Folder deployment | Dedicated CLI | Handles packaging and binary upload |
| Stream deployment logs | Dedicated CLI | Handles SSE/streaming and terminal output |
| Route not wrapped by CLI | `openship api` | Keeps context and authentication inside Openship |
| Discover current request schema | MCP `tools/list` | Live permission-filtered JSON Schema |
| Discover guided multi-step flow | MCP `prompts/list` / `prompts/get` | Live tool names and ordered workflow |
| OAuth, GitHub App installation, `flowHref` | UI/out of band | Deliberately requires user interaction |
| Interactive terminal/PTY | UI or dedicated supported client | Not equivalent to a normal JSON REST call |

Use the narrowest channel that supports the complete operation safely.

## 2. Discovery sequence

Before selecting a channel:

```bash
openship --version
openship --json status
openship <area> --help
```

For a specific subcommand:

```bash
openship <area> <action> --help
```

For schema discovery:

```bash
python3 scripts/mcp_catalog.py --kind tools --search '<resource-or-action>'
```

If the current CLI has a dedicated command, prefer it unless exact REST control is necessary.

## 3. Dedicated CLI

Use the CLI for:

- `up`, `stop`, `status`, `doctor`, `update`, `uninstall`;
- `login`, `logout`, `context`, `token`, `init`, `config`;
- `project`, `service`, `domain`, `edge`;
- `deploy`, `deployment`, `logs`;
- `server`, `system`, `mail`, `backup`.

The precise command tree is version-dependent. Inspect help rather than copying stale flags.

Prefer global JSON mode for state reads:

```bash
openship --json project list
openship --json service list --project proj_xxx
```

Keep stdout machine-readable. Capture human-readable diagnostics from stderr separately when scripting.

Avoid interactive prompts in unattended execution. Use an explicit non-interactive or confirmation flag only after the safety guard has been satisfied.

## 4. Authenticated REST

Use the CLI's API escape hatch:

```bash
openship --json api /projects
openship --json api /projects/proj_xxx --method GET
openship --json api /projects/proj_xxx --method PATCH --data '{"name":"new-name"}'
openship --json api /projects --query perPage=100
```

Rules:

- path is under `/api`;
- default method is GET, or POST when data is supplied;
- request data is JSON;
- query parameters use repeated `--query key=value` according to live help;
- use the current schema before POST, PUT, or PATCH;
- parse non-2xx responses as failures even if they contain useful JSON.

Do not use raw `curl` merely to avoid learning `openship api`. Raw HTTP is justified for binary uploads that the platform explicitly returns as an out-of-band step.

## 5. MCP discovery

The instance exposes a stateless JSON-RPC endpoint at `/api/mcp`. The bundled helper reaches it through `openship api`, so it does not read or print the PAT.

```bash
python3 scripts/mcp_catalog.py --kind tools
python3 scripts/mcp_catalog.py --kind tools --search projects
python3 scripts/mcp_catalog.py --kind tools --mutating --safe-only
python3 scripts/mcp_catalog.py --kind prompts
```

Use each tool's:

- `name`;
- `description`;
- `inputSchema`;
- `readOnly` annotation;
- `destructive` annotation.

A tool may be absent because:

- the route did not opt into MCP;
- the current role/token cannot use it;
- the instance mode hides it;
- repository content access was not granted;
- the installed server version predates it.

Do not broaden credentials merely to make a convenient tool appear. First determine whether the task can use a dedicated CLI or ordinary REST route within the existing scope.

## 6. UI and out-of-band steps

Surface the exact user action when the response provides:

- OAuth or PKCE authorization URL;
- GitHub App installation flow;
- `flowHref` for a wizard application;
- browser-only administrative step;
- raw tarball or other binary upload target;
- interactive terminal/PTY requirement.

Do not claim the flow is complete until the user step has been performed and the resulting control-plane state can be read.

## 7. Fallback and failure rules

Use this fallback order:

```text
dedicated CLI
→ openship api with confirmed route/schema
→ MCP-discovered tool or guided prompt
→ explicit UI/out-of-band user step
→ stop with missing capability
```

Stop when:

- help and live schema disagree in a way that affects a write;
- the endpoint or body remains uncertain;
- the selected token does not expose the required scope;
- the operation would require reading a credential file;
- the only apparent route is intentionally excluded from automation.

Report the missing capability precisely rather than attempting a neighboring action with different semantics.
