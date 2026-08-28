from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "openship" / "scripts" / "mcp_catalog.py"
FIXTURES = ROOT / "tests" / "fixtures"

spec = importlib.util.spec_from_file_location("openship_mcp_catalog", SCRIPT)
assert spec and spec.loader
catalog = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = catalog
spec.loader.exec_module(catalog)


class McpCatalogTests(unittest.TestCase):
    def fixture(self, name: str):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def test_normalize_and_filter_tools(self):
        tools = catalog.normalize_tools(self.fixture("mcp_tools.json"))
        self.assertEqual(len(tools), 3)
        self.assertTrue(next(tool for tool in tools if tool["name"] == "get_projects_by_id")["readOnly"])

        safe_mutations = catalog.filter_tools(
            tools,
            search="service",
            read_mode="mutating",
            risk_mode="safe-only",
        )
        self.assertEqual([tool["name"] for tool in safe_mutations], ["patch_projects_by_id_services_by_serviceId"])

        destructive = catalog.filter_tools(
            tools,
            search=None,
            read_mode=None,
            risk_mode="destructive",
        )
        self.assertEqual([tool["name"] for tool in destructive], ["delete_projects_by_id"])

    def test_normalize_prompts(self):
        prompts = catalog.normalize_prompts(self.fixture("mcp_prompts.json"))
        self.assertEqual(prompts[0]["name"], "deploy-from-git")
        self.assertEqual(prompts[0]["arguments"][0]["name"], "repo")

    def test_rpc_request_uses_cli_without_token_argument(self):
        response = self.fixture("mcp_tools.json")
        captured = {}

        def fake_run(args, *, cwd, timeout):
            captured["args"] = list(args)
            return catalog.CommandResult(tuple(args), 0, json.dumps(response), "")

        with mock.patch.object(catalog._mcp_client, "run_command", side_effect=fake_run):
            result = catalog.rpc_request(
                "/usr/bin/openship",
                "tools/list",
                request_id=1,
                params=None,
                timeout=1.0,
            )

        self.assertEqual(result["result"]["tools"][0]["name"], "get_projects_by_id")
        rendered = " ".join(captured["args"])
        self.assertIn("api /mcp", rendered)
        self.assertNotIn("Bearer", rendered)
        self.assertNotIn("opsh_", rendered)

    def test_json_rpc_error_is_sanitized(self):
        response = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32600, "message": "bad Bearer topsecret"},
        }
        with mock.patch.object(
            catalog._mcp_client,
            "run_command",
            return_value=catalog.CommandResult(("openship",), 1, json.dumps(response), ""),
        ):
            with self.assertRaises(catalog.CatalogError) as ctx:
                catalog.rpc_request("openship", "tools/list", request_id=1, params=None, timeout=1.0)
        self.assertNotIn("topsecret", str(ctx.exception))
        self.assertIn("<redacted>", str(ctx.exception))

    def test_build_catalog_counts(self):
        args = argparse.Namespace(
            openship="openship",
            kind="all",
            timeout=1.0,
            search=None,
            read_mode=None,
            risk_mode=None,
        )

        def fake_rpc(binary, method, *, request_id, params, timeout):
            return self.fixture("mcp_tools.json" if method == "tools/list" else "mcp_prompts.json")

        with mock.patch.object(catalog.shutil, "which", return_value="/usr/bin/openship"), mock.patch.object(
            catalog, "rpc_request", side_effect=fake_rpc
        ):
            result = catalog.build_catalog(args)

        self.assertEqual(result["counts"]["rawTools"], 3)
        self.assertEqual(result["counts"]["destructiveTools"], 1)
        self.assertEqual(result["counts"]["returnedPrompts"], 1)


if __name__ == "__main__":
    unittest.main()
