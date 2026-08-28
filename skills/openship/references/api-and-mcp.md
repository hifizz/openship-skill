# REST API and MCP capability discovery

## Contents

1. Authenticated API access
2. JSON output and errors
3. Schema discipline
4. MCP endpoint and methods
5. Permission-filtered tools
6. Guided prompts
7. Safe catalog workflow
8. Fallback rules

## 1. Authenticated API access

Prefer:

```bash
openship --json api /path
openship --json api /path --method POST --data '{"key":"value"}'
```

The CLI owns:

- active context selection;
- API base URL;
- bearer credential injection;
- JSON/raw response printing;
- non-zero status for failed responses.

Do not read the PAT from disk to build a manual request.

Use query parameters only in the form supported by live help. URL-encode path identifiers and user-supplied values through the CLI/client rather than string concatenation when writing helper code.

## 2. JSON output and errors

Global JSON mode reserves stdout for structured data. Human information and errors may be written to stderr.

When automating:

- parse stdout even if the process exits non-zero; an API error body can still be structured;
- treat non-zero exit or non-2xx response as failure;
- redact bearer/PAT-looking strings in diagnostics;
- bound output and timeouts;
- do not retry mutations automatically unless the operation is idempotent and the failure is proven pre-dispatch.

Common classes:

- 400: invalid body/query/state;
- 401: missing/invalid/expired credential;
- 403: authenticated but not permitted;
- 404: resource absent or intentionally hidden by scope;
- 409: conflict/stale config/pending condition;
- 429: rate limited;
- 5xx: platform/runtime failure.

Preserve returned machine error codes when available.

## 3. Schema discipline

Before POST/PUT/PATCH:

1. inspect a dedicated CLI command's help;
2. search the live MCP catalog for the route/action;
3. inspect current official route/schema if needed;
4. GET the target resource;
5. construct the narrow body;
6. validate replacement/merge semantics;
7. execute once;
8. GET the result.

Do not send permissive blobs or unknown fields. MCP tools only include a structured `body` when the route exposes a schema; absence of `body` can mean a no-body action.

## 4. MCP endpoint and methods

Openship exposes stateless Streamable HTTP JSON-RPC at:

```text
POST /api/mcp
```

The server supports methods including:

- `initialize`;
- `ping`;
- `tools/list`;
- `tools/call`;
- `prompts/list`;
- `prompts/get`;
- `notifications/initialized`.

GET is not an SSE stream for this endpoint.

Reach it safely through `openship api`:

```bash
openship --json api /mcp --method POST --data \
  '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

The bundled `mcp_catalog.py` handles normalization and filtering.

## 5. Permission-filtered tools

The tool catalog is generated from routes that explicitly opt into MCP. It is filtered by:

- role;
- read-only token mode;
- resource grants;
- GitHub account/repository grant width;
- repository content/write capability;
- self-host/cloud availability;
- hard-denied credential/auth surfaces.

`tools/list` is capability hygiene, not the final authorization gate. Every `tools/call` re-enters the real API auth, validation, routing, and per-resource permission checks.

Interpret absence carefully:

- token/auth routes are intentionally absent;
- secret reveal routes may be intentionally absent;
- an org-wide list may be hidden from a scoped token;
- a resource-specific tool may be listed but return 404 for an ungranted ID;
- GitHub deploy/metadata access may exist without file-content access.

Do not ask for broader permissions until the task genuinely requires them.

## 6. Guided prompts

`prompts/list` exposes multi-step workflows, such as:

- overview/orientation;
- deploy from Git;
- deploy a folder;
- install a catalog app.

Use `prompts/get` when a flat tool list does not explain sequencing or out-of-band steps. Prompt text resolves live tool names, reducing route-name drift.

Treat prompt guidance as an execution plan, then apply this skill's context and risk guards before mutation.

## 7. Safe catalog workflow

Examples:

```bash
python3 scripts/mcp_catalog.py --kind tools
python3 scripts/mcp_catalog.py --kind tools --search deployment
python3 scripts/mcp_catalog.py --kind tools --mutating --safe-only
python3 scripts/mcp_catalog.py --kind tools --destructive
python3 scripts/mcp_catalog.py --kind prompts
python3 scripts/mcp_catalog.py --kind all --output .mcp-catalog.json
```

The normalized output contains:

```text
name
description
readOnly
destructive
inputSchema
```

Do not commit instance-specific catalogs unless intentionally documenting a public test environment. A catalog can reveal resource/action names even though it contains no token.

## 8. Fallback rules

If MCP is unavailable:

1. use dedicated CLI help;
2. use confirmed REST docs/source for the current version;
3. inspect actual GET responses;
4. stop before an uncertain write.

If the CLI API call cannot reach `/api/mcp`, distinguish:

- API unreachable;
- not logged in;
- server version without MCP;
- route disabled by deployment mode;
- invalid token;
- rate limit.

Do not fall back to reading the local credential file.
