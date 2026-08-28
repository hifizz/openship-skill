# Secret exposure, build logs, environment variables, and safe output

## Contents

1. Security invariant
2. When the gate is mandatory
3. Sources and sinks
4. Evidence and fail-closed decisions
5. Build and deploy review
6. Environment-variable operations
7. Safe output and leak response
8. Disposable canary verification
9. Operator checklist

## 1. Security invariant

The primary invariant is:

> No plaintext user secret may enter model context, a displayed command, a persisted operation record, or an unverified output sink.

Prevent emission first. Redaction is only a second line of defense. If a secret was already written to an Openship build log, Docker output, CI log, deployment error, API response, or tool result, hiding it in the final answer does not undo the exposure.

Never use a real credential to test whether a path is safe.

## 2. When the gate is mandatory

Run the bundled Secret Exposure Gate before:

- `build` or `deploy`;
- reading build/runtime logs that may contain environment values;
- listing, reading, creating, or changing environment variables;
- changing a Service, Compose definition, image, command, build args, or startup command;
- container exec;
- database commands that may print a connection string;
- backup or restore jobs that may log credentials;
- calling an API or MCP tool whose response may include environment values.

Use:

```bash
python3 scripts/secret_exposure_preflight.py \
  --cwd "$PWD" \
  --operation deploy \
  --remote-env-state unknown \
  --fail-closed
```

A default `unknown` remote environment is intentional. Before a build/deploy, determine through secret-safe metadata whether the selected project/environment has no sensitive variables (`none`) or has one or more (`present`). Never retrieve plaintext merely to make this classification.

## 3. Sources and sinks

### Sensitive sources

Classify at least:

- `.env`, `.env.local`, `.env.production`, and equivalent files;
- project/service environment-variable keys and secret flags;
- database/Redis/SMTP URLs;
- API/OAuth/JWT credentials;
- registry credentials;
- SSH/private-key/keystore files;
- Docker build arguments;
- Compose `env_file` and interpolated environment;
- the local process environment;
- mounted secret files;
- hard-coded credential URLs or private-key blocks.

The static scanner returns paths and key names only. It must not return values or source snippets.

### Output sinks

For the selected operation, classify every relevant sink:

```text
CLI stdout / stderr
shell command line and history
Agent transcript / tool result
REST API response
MCP response
OpenShip build log
OpenShip runtime or job log
Docker/BuildKit history
build artifact or generated static file
backup artifact
container exec stdout / stderr
```

A local sanitizer protects only what it emits. It does not prove that upstream storage is safe.

## 4. Evidence and fail-closed decisions

Accepted evidence should be tied to the current CLI/server version and operation path:

1. live CLI help and current API/MCP schema;
2. current official source or documentation that explicitly defines masking/write-only behavior;
3. a disposable canary test using a fake value in a disposable project;
4. a narrowly scoped operator assertion only when the preceding evidence cannot be automated.

Provide evidence using a JSON file compatible with `schemas/secret-exposure-evidence.schema.json`:

```json
{
  "schemaVersion": 1,
  "instanceVersion": "0.6.8",
  "checkedAt": "2026-08-28T08:00:00Z",
  "sinks": {
    "buildLog": {
      "status": "masked",
      "method": "disposable-canary",
      "scope": "git build on self-hosted 0.6.8"
    },
    "apiResponse": {
      "status": "metadata-only",
      "method": "live-schema"
    }
  }
}
```

Then run:

```bash
python3 scripts/secret_exposure_preflight.py \
  --operation build \
  --remote-env-state present \
  --evidence-file /secure/path/evidence.json \
  --fail-closed
```

Decision meanings:

- `allow`: no sensitive source was identified and no blocking pattern exists;
- `allow-with-redaction`: a sensitive path is proven non-plaintext, but all displayed output must still be sanitized/minimized;
- `require-out-of-band-entry`: a new secret needs a write-only or interactive value-entry path outside the Agent transcript;
- `blocked`: output behavior, remote secret presence, or configuration remains unsafe/unknown.

Unknown output behavior is blocking whenever sensitive data may be touched.

## 5. Build and deploy review

Before starting work, inspect build-related configuration without printing values:

```text
package.json scripts
Dockerfile / Containerfile
Compose files
openship.json
Makefile / task runner files
shell scripts
CI workflows
framework build hooks
```

Block high-confidence leak patterns such as:

```text
printenv or a complete `env` dump
set -x / shell xtrace
console.log(process.env)
JSON.stringify(process.env)
print(os.environ)
cat .env
printing a sensitive variable with echo/printf
credential-bearing database URLs
private keys embedded in config
sensitive Docker ARG/ENV or --build-arg use
```

Docker `ARG` and command-line `--build-arg` are not automatically safe secret transports. They can be echoed, persisted in image metadata/history, or captured by build tooling. Use them for sensitive data only when the exact build backend and mechanism have been verified as secret-safe. Prefer a platform-supported ephemeral secret mount when available.

A dirty Git worktree and a folder upload have different exposure surfaces. Folder upload must exclude credential files; Git deployment still needs remote environment and build-log checks.

## 6. Environment-variable operations

Default to key/metadata operations:

```text
key name
scope/environment
isSecret or masked status
updatedAt
source/owner when safe
```

Do not request or display plaintext values.

For updates:

- preserve masked sentinels;
- change only the requested key;
- do not send all current environment variables back as a replacement object unless live semantics require it and secret values can be preserved without retrieval;
- do not place a value in a displayed shell command, JSON argument, log, source file, or operation journal;
- prefer an interactive/write-only CLI or Dashboard flow for the value;
- verify afterward using key metadata, not value echoing.

If the only available API requires a plaintext value in a command argument/tool result, return `require-out-of-band-entry` rather than exposing it.

## 7. Safe output and leak response

Before showing a bounded CLI/API/log payload to the Agent, pipe it through:

```bash
some-command 2>&1 | python3 scripts/log_leak_scan.py --fail-on-detection
```

Or sanitize a selected file/range:

```bash
python3 scripts/log_leak_scan.py /tmp/selected-log.txt \
  --report /tmp/leak-report.json \
  --fail-on-detection
```

The scanner redacts common bearer/PAT/API-key/JWT/private-key/credential-URL/assignment forms and disposable canaries. Its report contains categories and counts only.

Do not stream an unbounded log into model context. Select the smallest relevant range first.

When a canary or probable real credential is detected:

1. stop displaying additional output;
2. record only sink, category, operation ID, and time;
3. determine whether the raw value was persisted upstream;
4. contain access to the affected log/artifact;
5. advise credential rotation when a real credential may have been exposed;
6. do not repeat the credential while explaining the incident;
7. mark that operation path unsafe until remediated and reverified.

## 8. Disposable canary verification

Use a unique fake marker, never a real credential, for example:

```text
OPENSHIP_SECRET_CANARY_<random-id>
```

Use a disposable project/environment and exercise the same path as production:

```text
write canary through the intended secret input mechanism
trigger the same build/deploy path
read build/runtime/deployment/API/MCP outputs
inspect generated artifact and image metadata where applicable
scan every bounded output for the marker
remove the disposable resource
```

A canary appearing in any persistent sink means the path is `plaintext` and blocked. A canary not appearing is evidence only for the tested version, mode, operation, and output surface; record that scope.

Never put the canary value into the evidence file. Record only that a generated canary was absent/present.

## 9. Operator checklist

Before sensitive work:

```text
[ ] Exact context/project/environment resolved
[ ] Remote environment classified without plaintext retrieval
[ ] Local sensitive-file names and safe key metadata inspected
[ ] Build/config leak patterns scanned
[ ] Every relevant sink classified
[ ] Evidence matches current version and execution path
[ ] Secret input is write-only/out of band when setting values
[ ] Decision is allow or allow-with-redaction
```

Afterward:

```text
[ ] Displayed output passed local leak scanning
[ ] No secret value entered command history or journal
[ ] Build/deployment reached terminal state
[ ] Verification used metadata/health/application behavior, not value echoing
[ ] Any detected leak was contained and the affected credential considered for rotation
```
