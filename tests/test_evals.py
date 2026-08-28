from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class EvalFixtureTests(unittest.TestCase):
    def assert_eval_pair(self, version: str, schema_version: int, minimum: int) -> None:
        cases = json.loads((ROOT / "evals" / "cases" / f"{version}.json").read_text(encoding="utf-8"))
        expected = json.loads((ROOT / "evals" / "expected" / f"{version}.json").read_text(encoding="utf-8"))
        self.assertEqual(cases["schemaVersion"], schema_version)
        self.assertEqual(expected["schemaVersion"], schema_version)

        case_ids = [item["id"] for item in cases["cases"]]
        expected_ids = [item["id"] for item in expected["expectations"]]
        self.assertEqual(len(case_ids), len(set(case_ids)))
        self.assertEqual(set(case_ids), set(expected_ids))
        self.assertGreaterEqual(len(case_ids), minimum)

        for item in cases["cases"]:
            self.assertTrue(item["prompt"].strip())
            self.assertIsInstance(item["context"], dict)
        for item in expected["expectations"]:
            self.assertIsInstance(item["trigger"], bool)
            self.assertIn(item["risk"], {None, "R0", "R1", "R2", "R3"})
            self.assertIsInstance(item["must"], list)
            self.assertIsInstance(item["mustNot"], list)
            if schema_version >= 2:
                self.assertIn(
                    item["secretDecision"],
                    {"allow", "allow-with-redaction", "require-out-of-band-entry", "blocked"},
                )

    def test_v01_cases_and_expectations_align(self):
        self.assert_eval_pair("v0.1", 1, 15)

    def test_v02_secret_cases_and_expectations_align(self):
        self.assert_eval_pair("v0.2", 2, 12)
        expected = json.loads((ROOT / "evals" / "expected" / "v0.2.json").read_text(encoding="utf-8"))
        decisions = {item["secretDecision"] for item in expected["expectations"]}
        self.assertIn("blocked", decisions)
        self.assertIn("allow-with-redaction", decisions)
        self.assertIn("require-out-of-band-entry", decisions)


if __name__ == "__main__":
    unittest.main()
