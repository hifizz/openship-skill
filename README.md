# Openship Operator Skill

A version-aware Agent Skill for safely operating [Openship](https://openship.io) projects, deployments, Services, domains, and self-hosted infrastructure through the local `openship` CLI, authenticated REST API, and MCP capability catalog.

## V0.2: Secret-safe builds and operations

V0.2 keeps the V0.1 context/routing/risk model and adds a fail-closed Secret Exposure Gate:

- no build/deploy starts until local secret sources, remote environment state, and relevant output sinks are classified;
- unknown or plaintext output behavior blocks work whenever sensitive data may be touched;
- environment-variable operations default to key/metadata only;
- new Secret values require a proven interactive/write-only or out-of-band input path;
- repository scanning detects environment dumps, shell xtrace, `process.env`/`os.environ` serialization, `.env` output, credential URLs, inline private keys, sensitive variable echoing, and unsafe Docker build arguments;
- bounded CLI/API/log output can be sanitized locally before it reaches Agent context;
- disposable fake-canary evidence is supported, while real secrets are explicitly prohibited as test values;
- JSON Schemas, tests, evals, and CI enforce the security contract.

The key invariant is:

> No plaintext user secret may enter model context, a displayed command, a persisted operation record, or an unverified output sink.

Redaction after Openship, Docker, CI, or another backend has persisted a plaintext value is not considered prevention.

## Repository layout

```text
skills/openship/
├── SKILL.md
├── VERSION
├── agents/openai.yaml
├── references/
├── schemas/
└── scripts/

tests/                 # deterministic unit and structure tests
evals/                 # trigger, routing, context, and safety cases
upstream/               # reviewed Openship release/source baseline
.github/workflows/      # validation and upstream drift checks
```

## Install

Clone the repository, then copy or symlink `skills/openship` into the skills directory used by your Agent.

### Codex

```bash
git clone https://github.com/hifizz/openship-skill.git
mkdir -p ~/.agents/skills
ln -s "$(pwd)/openship-skill/skills/openship" ~/.agents/skills/openship
```

### Claude Code

```bash
git clone https://github.com/hifizz/openship-skill.git
mkdir -p ~/.claude/skills
ln -s "$(pwd)/openship-skill/skills/openship" ~/.claude/skills/openship
```

Restart the Agent after installation.

## Example requests

```text
Use the Openship skill to inspect this repository and tell me which project and instance it targets.

Before deploying, verify that project secrets cannot appear in build logs or Agent output, then deploy and follow it to completion.

Add pgvector support to the PostgreSQL Service managed by Openship without losing data or printing DATABASE_URL.

List environment-variable keys and secret metadata for production, but never retrieve or display values.

Diagnose why this Openship deployment is action_required and show only sanitized evidence.
```

## Deterministic helpers

### Context preflight

```bash
python3 skills/openship/scripts/preflight.py --cwd "$PWD"
```

### Secret Exposure Gate

A default unknown remote environment intentionally blocks sensitive operations:

```bash
python3 skills/openship/scripts/secret_exposure_preflight.py \
  --cwd "$PWD" \
  --operation deploy \
  --remote-env-state unknown \
  --fail-closed
```

After secret-safe metadata inspection and evidence collection:

```bash
python3 skills/openship/scripts/secret_exposure_preflight.py \
  --operation deploy \
  --remote-env-state present \
  --evidence-file /secure/path/evidence.json \
  --fail-closed
```

The plan reports paths, key names, pattern IDs, sink states, and decisions only. It never reports values or matching source snippets.

### Bounded output sanitizer

```bash
some-command 2>&1 | \
  python3 skills/openship/scripts/log_leak_scan.py --fail-on-detection
```

Or scan a selected file/range:

```bash
python3 skills/openship/scripts/log_leak_scan.py selected.log \
  --report /tmp/leak-report.json \
  --fail-on-detection
```

This is a second line of defense. It cannot remove plaintext already persisted upstream.

### MCP capability catalog

```bash
python3 skills/openship/scripts/mcp_catalog.py --kind tools --search service
```

All helpers use Python's standard library only. They never read `~/.openship/config.json` and never print bearer credentials intentionally.

## Validate

```bash
python3 -m compileall skills/openship/scripts tests
python3 -m unittest discover -s tests -v
```

## Upstream baseline

The reviewed Openship baseline remains `v0.6.8` at commit `fcadb4a52fb490ace7d9605d3bb0e2e5269e0e11`, checked on 2026-08-28. `upstream/openship.lock.json` records the machine-readable baseline and Skill version.

## License

MIT. See `LICENSE` and `skills/openship/LICENSE.txt`.
