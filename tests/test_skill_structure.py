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
            SKILL_DIR / "agents" / "openai.yaml",
            SKILL_DIR / "scripts" / "preflight.py",
            SKILL_DIR / "scripts" / "mcp_catalog.py",
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
        self.assertGreaterEqual(len(references), 8)
        for relative in references:
            self.assertTrue((SKILL_DIR / relative).is_file(), relative)

    def test_openai_metadata_matches_skill(self):
        text = (SKILL_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn('display_name: "Openship Operator"', text)
        self.assertIn("$openship", text)
        self.assertRegex(text, r'short_description: "[^\n]{25,64}"')

    def test_no_instruction_to_dump_credential_file(self):
        corpus = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [SKILL, *sorted((SKILL_DIR / "references").glob("*.md"))]
        )
        self.assertNotRegex(corpus, r"(?i)\bcat\s+[^\n]*\.openship/config\.json")
        self.assertNotRegex(corpus, r"(?i)\bgrep\s+[^\n]*opsh_")

    def test_upstream_lock_is_valid(self):
        data = json.loads((ROOT / "upstream" / "openship.lock.json").read_text(encoding="utf-8"))
        self.assertEqual(data["release"], "v0.6.8")
        self.assertRegex(data["mainCommit"], r"^[0-9a-f]{40}$")
        self.assertEqual(data["sourceOfTruthOrder"][0], "installed CLI help and version")


if __name__ == "__main__":
    unittest.main()
