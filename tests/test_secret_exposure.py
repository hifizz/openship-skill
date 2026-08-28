from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "skills" / "openship" / "scripts"
MODULE = SCRIPT_DIR / "_secret_exposure.py"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

spec = importlib.util.spec_from_file_location("openship_secret_exposure", MODULE)
assert spec and spec.loader
secret = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = secret
spec.loader.exec_module(secret)


class SecretExposureTests(unittest.TestCase):
    def safe_evidence(self, root: Path, operation: str) -> Path:
        sinks = {
            name: {"status": "write-only" if name == "secretInput" else "masked", "method": "disposable-canary"}
            for name in secret.OPERATION_SINKS[operation]
            if name != "agentTranscript"
        }
        path = root / "evidence.json"
        path.write_text(json.dumps({"schemaVersion": 1, "sinks": sinks}), encoding="utf-8")
        return path

    def test_env_file_reports_keys_but_never_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            value = "super-secret-value-that-must-not-appear"
            (root / ".env.production").write_text(
                f"DATABASE_URL=postgresql://user:{value}@db/app\nFEATURE_FLAG=true\n",
                encoding="utf-8",
            )
            scan = secret.scan_repository(root)
            rendered = json.dumps(scan)
            self.assertNotIn(value, rendered)
            self.assertIn("DATABASE_URL", rendered)
            self.assertIn("FEATURE_FLAG", rendered)
            self.assertIn("environment-file", rendered)

    def test_build_blocks_when_remote_environment_is_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = secret.build_exposure_plan(
                root=Path(tmp),
                operation="build",
                remote_env_state="unknown",
            )
            self.assertEqual(plan["decision"], "blocked")
            self.assertTrue(plan["touchesSensitiveData"])
            self.assertTrue(any("unknown" in reason.lower() for reason in plan["blockingReasons"]))

    def test_dangerous_build_script_is_blocking_without_echoing_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = '{"scripts":{"build":"env && node build.js"}}\n'
            (root / "package.json").write_text(source, encoding="utf-8")
            evidence = self.safe_evidence(root, "build")
            plan = secret.build_exposure_plan(
                root=root,
                operation="build",
                remote_env_state="none",
                evidence_file=evidence,
            )
            self.assertEqual(plan["decision"], "blocked")
            self.assertIn("ENV_DUMP_COMMAND", {item["code"] for item in plan["findings"]})
            rendered = json.dumps(plan)
            self.assertNotIn("env && node build.js", rendered)

    def test_sensitive_docker_arg_is_blocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Dockerfile").write_text("FROM node:22\nARG DATABASE_URL\nRUN npm run build\n", encoding="utf-8")
            evidence = self.safe_evidence(root, "build")
            plan = secret.build_exposure_plan(
                root=root,
                operation="build",
                remote_env_state="none",
                evidence_file=evidence,
            )
            codes = {item["code"] for item in plan["findings"]}
            self.assertIn("DOCKER_SECRET_DECLARATION", codes)
            self.assertEqual(plan["decision"], "blocked")

    def test_present_secrets_with_verified_sinks_are_allowed_with_redaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = self.safe_evidence(root, "deploy")
            plan = secret.build_exposure_plan(
                root=root,
                operation="deploy",
                remote_env_state="present",
                evidence_file=evidence,
                sensitive_keys=["DATABASE_URL"],
            )
            self.assertEqual(plan["decision"], "allow-with-redaction")
            self.assertFalse(plan["blockingReasons"])
            rendered = json.dumps(plan)
            self.assertNotIn("secret-value", rendered)
            self.assertNotIn("hunter2", rendered)

    def test_env_write_requires_write_only_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence_data = {
                "schemaVersion": 1,
                "sinks": {
                    name: {"status": "masked", "method": "live-schema"}
                    for name in secret.OPERATION_SINKS["env-write"]
                    if name not in {"agentTranscript", "secretInput"}
                },
            }
            evidence = root / "evidence.json"
            evidence.write_text(json.dumps(evidence_data), encoding="utf-8")
            plan = secret.build_exposure_plan(
                root=root,
                operation="env-write",
                remote_env_state="present",
                evidence_file=evidence,
                sensitive_keys=["OPENAI_API_KEY"],
            )
            self.assertEqual(plan["decision"], "require-out-of-band-entry")

    def test_plaintext_sink_blocks_even_with_other_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = self.safe_evidence(root, "logs")
            data = json.loads(evidence.read_text(encoding="utf-8"))
            data["sinks"]["requestedLog"] = {"status": "plaintext", "method": "disposable-canary"}
            evidence.write_text(json.dumps(data), encoding="utf-8")
            plan = secret.build_exposure_plan(
                root=root,
                operation="logs",
                remote_env_state="present",
                evidence_file=evidence,
            )
            self.assertEqual(plan["decision"], "blocked")
            self.assertEqual(plan["sinks"]["requestedLog"]["status"], "plaintext")

    def test_plan_schema_forbids_secret_value_fields(self):
        schema = json.loads(
            (ROOT / "skills" / "openship" / "schemas" / "secret-exposure-plan.schema.json").read_text(encoding="utf-8")
        )
        source_properties = schema["properties"]["sources"]["items"]["properties"]
        self.assertNotIn("value", source_properties)
        self.assertEqual(source_properties["valuesReturned"]["const"], False)


if __name__ == "__main__":
    unittest.main()
