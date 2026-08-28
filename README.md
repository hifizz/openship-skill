# Openship Operator Skill

A version-aware Agent Skill for safely operating [Openship](https://openship.io) projects, deployments, services, domains, and self-hosted infrastructure through the local `openship` CLI, authenticated REST API, and MCP capability catalog.

## V0.1 scope

V0.1 establishes the operating contract rather than reimplementing the platform:

- resolve the active Openship context, current repository, and linked project;
- discover capabilities from the installed CLI and connected instance;
- route work across dedicated CLI commands, `openship api`, MCP discovery, and out-of-band UI flows;
- classify operational risk before mutation;
- protect tokens, masked secrets, volumes, and stateful services;
- read state before changes and verify state after changes;
- provide deterministic `preflight.py` and `mcp_catalog.py` helpers;
- ship tests, evaluation fixtures, and upstream-drift checks.

High-risk infrastructure mutations remain deliberately guarded. The skill may plan them, but it must not infer authorization from vague language or bypass Openship's own permission model.

## Repository layout

```text
skills/openship/
├── SKILL.md
├── agents/openai.yaml
├── references/
└── scripts/

tests/                 # deterministic unit and structure tests
evals/                 # trigger, routing, context, and safety cases
upstream/               # reviewed Openship release/source baseline
.github/workflows/      # validation and upstream drift checks
```

## Install

Clone the repository, then copy or symlink `skills/openship` into the skills directory used by your agent.

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

Restart the agent after installation.

## Example requests

```text
Use the Openship skill to inspect this repository and tell me which project and instance it targets.

Deploy the current branch to the linked Openship project, follow the deployment, and verify the result.

Add pgvector support to the PostgreSQL service managed by Openship without losing data.

Diagnose why this Openship deployment is in action_required and show the exact pending action.
```

## Deterministic helpers

Run a secret-safe context report:

```bash
python3 skills/openship/scripts/preflight.py --cwd "$PWD"
```

Inspect the live MCP tool catalog without reading the PAT file:

```bash
python3 skills/openship/scripts/mcp_catalog.py --kind tools --search service
```

Both helpers use Python's standard library only. They never read `~/.openship/config.json` and never print bearer credentials.

## Validate

```bash
python3 -m compileall skills/openship/scripts tests
python3 -m unittest discover -s tests -v
```

## Upstream baseline

The initial reviewed baseline is Openship `v0.6.8` at commit `fcadb4a52fb490ace7d9605d3bb0e2e5269e0e11`, checked on 2026-08-28. See `upstream/openship.lock.json` for the complete machine-readable record.

## License

MIT. See `LICENSE` and `skills/openship/LICENSE.txt`.
