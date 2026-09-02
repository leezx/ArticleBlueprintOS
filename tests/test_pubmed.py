import unittest
from pathlib import Path

from article_blueprint_os.pubmed import normalize_doi, parse_pubmed_xml


FIXTURE = Path(__file__).parent / "fixtures" / "pubmed_sample.xml"


class PubMedParserTests(unittest.TestCase):
    def test_parse_article_fields(self):
        records = parse_pubmed_xml(FIXTURE.read_bytes())
        self.assertEqual(2, len(records))
        article = records[0]
        self.assertEqual("40000001", article.pmid)
        self.assertEqual("10.1000/test.001", article.doi)
        self.assertEqual("2026-08-14", article.publication_date)
        self.assertEqual("day", article.publication_date_precision)
        self.assertIn("BACKGROUND:", article.abstract)
        self.assertEqual("Atlas Consortium", article.authors[1]["collective"])
        self.assertEqual(("Neoplasms", "Transcriptome"), article.mesh_terms)

    def test_medline_date_falls_back_to_year(self):
        article = parse_pubmed_xml(FIXTURE.read_bytes())[1]
        self.assertEqual("2025", article.publication_date)
        self.assertEqual("year", article.publication_date_precision)

    def test_normalize_doi(self):
        self.assertEqual("10.1/abc", normalize_doi("https://doi.org/10.1/ABC."))
        self.assertIsNone(normalize_doi("  "))


if __name__ == "__main__":
    unittest.main()
