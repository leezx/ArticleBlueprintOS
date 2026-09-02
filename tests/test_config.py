import json
import unittest
from pathlib import Path

from article_blueprint_os.config import load_journals, load_screening_rules
from article_blueprint_os.db import connect


ROOT = Path(__file__).resolve().parents[1]


class ConfigTests(unittest.TestCase):
    def test_registry_is_unique_and_excludes_pure_review_journal(self):
        registry = load_journals(ROOT / "config" / "journals.json")
        self.assertEqual(67, len(registry.journals))
        self.assertNotIn(
            "Nature Reviews Gastroenterology & Hepatology",
            {journal.title for journal in registry.journals},
        )
        self.assertEqual('"Cancer cell"[jour]', registry.by_key("cancer_cell").pubmed_term)
        self.assertIn("methods", registry.by_key("nature_biotechnology").tracks)

    def test_blacklist_is_disjoint_from_whitelist(self):
        registry = load_journals(ROOT / "config" / "journals.json")
        blacklist = json.loads((ROOT / "config" / "journal_blacklist.json").read_text())
        allowed = {journal.title.casefold() for journal in registry.journals}
        excluded = {title.casefold() for title in blacklist["exact_journals"]}
        self.assertFalse(allowed & excluded)
        self.assertIn("cancers", excluded)

    def test_rules_compile(self):
        import re

        rules = load_screening_rules(ROOT / "config" / "screening_rules.json")
        for pattern in (*rules.cancer, *rules.omics):
            re.compile(pattern)

    def test_database_payload_inside_repo_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside the repository"):
            connect(ROOT / "forbidden.sqlite3")


if __name__ == "__main__":
    unittest.main()
