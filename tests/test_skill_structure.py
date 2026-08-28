from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "openship"
SKILL = SKILL_DIR / "SKILL.md"


class SkillStructureTests(unittest.TestCase):
    def test_required_files_exist(self):
        required = [
            SKILL,
            SKILL_DIR / "VERSION",
            SKILL_DIR / "agents" / "openai.yaml",
            SKILL_DIR / "scripts" / "preflight.py",
            SKILL_DIR / "scripts" / "mcp_catalog.py",
            SKILL_DIR / "scripts" / "secret_exposure_preflight.py",
            SKILL_DIR / "scripts" / "log_leak_scan.py",
            SKILL_DIR / "schemas" / "secret-exposure-plan.schema.json",
            SKILL_DIR / "schemas" / "secret-exposure-evidence.schema.json",
            SKILL_DIR / "references" / "secrets.md",
            SKILL_DIR / "LICENSE.txt",
            ROOT / "upstream" / "openship.lock.json",
        ]
        for path in required:
            self.assertTrue(path.is_file(), path)

    def test_frontmatter_has_only_name_and_description(self):
        text = SKILL.read_text(encoding="utf-8")
        match = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
        self.assertIsNotNone(match)
        fields = []
        for line in match.group(1).splitlines():
            if line and not line.startswith((" ", "\t")) and ":" in line:
                fields.append(line.split(":", 1)[0].strip())
        self.assertEqual(fields, ["name", "description"])
        self.assertIn("name: openship", match.group(1))
        self.assertIn("OpenShift", match.group(1))

    def test_skill_is_progressively_disclosed(self):
        text = SKILL.read_text(encoding="utf-8")
        word_count = len(re.findall(r"\S+", text))
        self.assertLess(word_count, 5000)
        references = set(re.findall(r"\((references/[^)]+\.md)\)", text))
        self.assertGreaterEqual(len(references), 9)
        for relative in references:
            self.assertTrue((SKILL_DIR / relative).is_file(), relative)

    def test_openai_metadata_matches_skill(self):
        text = (SKILL_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn('display_name: "Openship Operator"', text)
        self.assertIn("$openship", text)
        self.assertRegex(text, r'short_description: "[^\n]{25,64}"')
        self.assertIn("Secret Exposure Gate", text)

    def test_no_instruction_to_dump_credential_file_or_values(self):
        corpus = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [SKILL, *sorted((SKILL_DIR / "references").glob("*.md"))]
        )
        self.assertNotRegex(corpus, r"(?i)\bcat\s+[^\n]*\.openship/config\.json")
        self.assertNotRegex(corpus, r"(?i)\bgrep\s+[^\n]*opsh_")
        self.assertIn("No plaintext user secret", corpus)
        self.assertIn("Redaction", corpus)

    def test_secret_schemas_forbid_value_output(self):
        plan = json.loads((SKILL_DIR / "schemas" / "secret-exposure-plan.schema.json").read_text(encoding="utf-8"))
        source_properties = plan["properties"]["sources"]["items"]["properties"]
        self.assertNotIn("value", source_properties)
        self.assertEqual(source_properties["valuesReturned"]["const"], False)

    def test_upstream_lock_is_valid(self):
        data = json.loads((ROOT / "upstream" / "openship.lock.json").read_text(encoding="utf-8"))
        self.assertEqual(data["release"], "v0.6.8")
        self.assertEqual(data["skillVersion"], "0.2.0")
        self.assertRegex(data["mainCommit"], r"^[0-9a-f]{40}$")
        self.assertEqual(data["sourceOfTruthOrder"][0], "installed CLI help and version")


if __name__ == "__main__":
    unittest.main()
