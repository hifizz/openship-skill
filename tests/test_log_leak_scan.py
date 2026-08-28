from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "skills" / "openship" / "scripts"
MODULE = SCRIPT_DIR / "_secret_exposure.py"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

spec = importlib.util.spec_from_file_location("openship_secret_sanitizer", MODULE)
assert spec and spec.loader
secret = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = secret
spec.loader.exec_module(secret)


class LogLeakScanTests(unittest.TestCase):
    def test_redacts_common_credentials_without_reporting_values(self):
        raw = "\n".join(
            [
                "Authorization: Bearer abc.def.ghi",
                "token=opsh_supersecrettoken",
                "DATABASE_URL=postgresql://app:hunter2@db:5432/app",
                '"OPENAI_API_KEY":"sk-abcdefghijklmnopqrstuvwxyz123456"',
                "jwt=eyJabcdefghijk.abcdefghijk.abcdefghijk",
                "-----BEGIN PRIVATE KEY-----\nabc123\n-----END PRIVATE KEY-----",
            ]
        )
        sanitized, detections = secret.sanitize_text(raw)
        for forbidden in ["abc.def.ghi", "opsh_supersecrettoken", "hunter2", "abcdefghijklmnopqrstuvwxyz123456", "abc123"]:
            self.assertNotIn(forbidden, sanitized)
        self.assertTrue(detections)
        self.assertNotIn("hunter2", str(detections))
        self.assertIn("<redacted", sanitized)

    def test_redacts_disposable_canary(self):
        marker = "OPENSHIP_SECRET_CANARY_12345"
        sanitized, detections = secret.sanitize_text(f"build said {marker}", canaries=[marker])
        self.assertNotIn(marker, sanitized)
        self.assertEqual(detections["canary"], 1)

    def test_non_secret_text_is_unchanged(self):
        raw = "service ready on port 3000\n"
        sanitized, detections = secret.sanitize_text(raw)
        self.assertEqual(sanitized, raw)
        self.assertEqual(detections, {})


if __name__ == "__main__":
    unittest.main()
