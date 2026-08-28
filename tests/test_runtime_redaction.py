from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "skills" / "openship" / "scripts"
MODULE = SCRIPT_DIR / "_runtime.py"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

spec = importlib.util.spec_from_file_location("openship_runtime_v02", MODULE)
assert spec and spec.loader
runtime = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runtime
spec.loader.exec_module(runtime)


class RuntimeRedactionTests(unittest.TestCase):
    def test_redact_covers_database_urls_and_assignments(self):
        raw = "DATABASE_URL=postgresql://app:hunter2@db/app Authorization: Bearer abc.def.ghi"
        output = runtime.redact(raw)
        self.assertNotIn("hunter2", output)
        self.assertNotIn("abc.def.ghi", output)
        self.assertIn("<redacted", output)

    def test_schema_version_is_v02(self):
        self.assertEqual(runtime.SCHEMA_VERSION, "0.2")


if __name__ == "__main__":
    unittest.main()
