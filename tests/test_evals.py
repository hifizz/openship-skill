from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class EvalFixtureTests(unittest.TestCase):
    def test_cases_and_expectations_align(self):
        cases = json.loads((ROOT / "evals" / "cases" / "v0.1.json").read_text(encoding="utf-8"))
        expected = json.loads((ROOT / "evals" / "expected" / "v0.1.json").read_text(encoding="utf-8"))
        self.assertEqual(cases["schemaVersion"], 1)
        self.assertEqual(expected["schemaVersion"], 1)

        case_ids = [item["id"] for item in cases["cases"]]
        expected_ids = [item["id"] for item in expected["expectations"]]
        self.assertEqual(len(case_ids), len(set(case_ids)))
        self.assertEqual(set(case_ids), set(expected_ids))
        self.assertGreaterEqual(len(case_ids), 15)

        for item in cases["cases"]:
            self.assertTrue(item["prompt"].strip())
            self.assertIsInstance(item["context"], dict)
        for item in expected["expectations"]:
            self.assertIsInstance(item["trigger"], bool)
            self.assertIn(item["risk"], {None, "R0", "R1", "R2", "R3"})
            self.assertIsInstance(item["must"], list)
            self.assertIsInstance(item["mustNot"], list)


if __name__ == "__main__":
    unittest.main()
