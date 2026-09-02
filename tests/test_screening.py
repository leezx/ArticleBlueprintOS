import unittest
from pathlib import Path

from article_blueprint_os.config import load_screening_rules
from article_blueprint_os.screening import screen_text


ROOT = Path(__file__).resolve().parents[1]


class ScreeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = load_screening_rules(ROOT / "config" / "screening_rules.json")

    def test_cancer_omics_original_is_priority_candidate(self):
        result = screen_text(
            self.rules,
            title="Pan-cancer single-cell atlas",
            abstract="Transcriptomic profiling of tumor ecosystems",
            mesh_terms=["Neoplasms"],
            article_types=["Journal Article"],
        )
        self.assertTrue(result.candidate_priority)
        self.assertTrue(result.cancer_terms)
        self.assertTrue(result.omics_terms)

    def test_missing_keywords_is_not_an_exclusion_state(self):
        result = screen_text(
            self.rules,
            title="A biological study",
            abstract="No keywords here",
            mesh_terms=[],
            article_types=["Journal Article"],
        )
        self.assertFalse(result.candidate_priority)
        self.assertFalse(result.obvious_non_original_type)

    def test_review_is_not_priority_even_with_keywords(self):
        result = screen_text(
            self.rules,
            title="Cancer genomics",
            abstract="A review of tumor single-cell studies",
            mesh_terms=[],
            article_types=["Review"],
        )
        self.assertFalse(result.candidate_priority)
        self.assertTrue(result.obvious_non_original_type)


if __name__ == "__main__":
    unittest.main()
