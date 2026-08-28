from __future__ import annotations

import importlib.util
import json
import tempfile
import sys
from contextlib import ExitStack
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "openship" / "scripts" / "preflight.py"
FIXTURES = ROOT / "tests" / "fixtures"

spec = importlib.util.spec_from_file_location("openship_preflight", SCRIPT)
assert spec and spec.loader
preflight = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = preflight
spec.loader.exec_module(preflight)


class PreflightTests(unittest.TestCase):
    def fixture(self, name: str):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def test_redacts_bearer_and_pat(self):
        text = "Authorization: Bearer abc.def and opsh_supersecrettoken"
        redacted = preflight.redact(text)
        self.assertNotIn("abc.def", redacted)
        self.assertNotIn("opsh_supersecrettoken", redacted)
        self.assertIn("<redacted>", redacted)

    def test_parse_json_with_prefix(self):
        self.assertEqual(preflight.parse_json_output('noise\n{"ok":true}'), {"ok": True})

    def test_project_link_is_allowlisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            link_dir = root / ".openship"
            link_dir.mkdir()
            (link_dir / "project.json").write_text(
                json.dumps(
                    {
                        "projectId": "proj_123",
                        "name": "demo",
                        "context": "production",
                        "defaults": {"environment": "preview"},
                        "token": "must-not-leak",
                    }
                ),
                encoding="utf-8",
            )
            report, error = preflight.read_project_link(root)
            self.assertIsNone(error)
            self.assertEqual(report["projectId"], "proj_123")
            self.assertEqual(report["environment"], "preview")
            self.assertNotIn("token", report)
            self.assertNotIn("must-not-leak", json.dumps(report))

    def fake_command(self, args, *, cwd, timeout):
        command = tuple(args)
        status = self.fixture("status.json")
        contexts = self.fixture("contexts.json")

        if command[-1] == "--version":
            return preflight.CommandResult(command, 0, "0.6.8\n", "")
        if "rev-parse" in command and "--is-inside-work-tree" in command:
            return preflight.CommandResult(command, 0, "true\n", "")
        if "rev-parse" in command and "--show-toplevel" in command:
            return preflight.CommandResult(command, 0, f"{cwd}\n", "")
        if "branch" in command and "--show-current" in command:
            return preflight.CommandResult(command, 0, "main\n", "")
        if "rev-parse" in command and command[-1] == "HEAD":
            return preflight.CommandResult(command, 0, "a" * 40 + "\n", "")
        if "status" in command and "--porcelain" in command:
            return preflight.CommandResult(command, 0, "", "")
        if "context" in command and "list" in command:
            return preflight.CommandResult(command, 0, json.dumps(contexts), "")
        if "status" in command:
            return preflight.CommandResult(command, 0, json.dumps(status), "")
        raise AssertionError(f"Unexpected command: {command}")

    def test_build_report_ready_and_context_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".openship").mkdir()
            (root / ".openship" / "project.json").write_text(
                json.dumps({"projectId": "proj_123", "context": "production"}),
                encoding="utf-8",
            )
            with ExitStack() as stack:
                stack.enter_context(mock.patch.object(preflight._preflight_core.shutil, "which", side_effect=lambda name: f"/usr/bin/{name}"))
                stack.enter_context(mock.patch.object(preflight._repository.shutil, "which", side_effect=lambda name: f"/usr/bin/{name}"))
                stack.enter_context(mock.patch.object(preflight._preflight_core, "run_command", side_effect=self.fake_command))
                stack.enter_context(mock.patch.object(preflight._repository, "run_command", side_effect=self.fake_command))
                stack.enter_context(mock.patch.object(preflight._openship, "run_command", side_effect=self.fake_command))
                report = preflight.build_report(root, 1.0)

            self.assertTrue(report["ready"])
            self.assertEqual(report["cli"]["version"], "0.6.8")
            self.assertTrue(report["instance"]["reachable"])
            self.assertEqual(report["instance"]["mode"], "self-hosted")
            self.assertTrue(report["projectLink"]["contextMatches"])
            self.assertEqual(report["repository"]["branch"], "main")
            self.assertFalse(report["errors"])

    def test_context_mismatch_is_blocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".openship").mkdir()
            (root / ".openship" / "project.json").write_text(
                json.dumps({"projectId": "proj_123", "context": "local"}),
                encoding="utf-8",
            )
            with ExitStack() as stack:
                stack.enter_context(mock.patch.object(preflight._preflight_core.shutil, "which", side_effect=lambda name: f"/usr/bin/{name}"))
                stack.enter_context(mock.patch.object(preflight._repository.shutil, "which", side_effect=lambda name: f"/usr/bin/{name}"))
                stack.enter_context(mock.patch.object(preflight._preflight_core, "run_command", side_effect=self.fake_command))
                stack.enter_context(mock.patch.object(preflight._repository, "run_command", side_effect=self.fake_command))
                stack.enter_context(mock.patch.object(preflight._openship, "run_command", side_effect=self.fake_command))
                report = preflight.build_report(root, 1.0)

            self.assertFalse(report["ready"])
            self.assertFalse(report["projectLink"]["contextMatches"])
            self.assertIn("CONTEXT_MISMATCH", {item["code"] for item in report["errors"]})

    def test_cli_missing_is_blocking_without_reading_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.object(preflight._preflight_core.shutil, "which", return_value=None):
                report = preflight.build_report(root, 1.0)
            self.assertFalse(report["ready"])
            self.assertIn("OPENSHIP_NOT_INSTALLED", {item["code"] for item in report["errors"]})


if __name__ == "__main__":
    unittest.main()
