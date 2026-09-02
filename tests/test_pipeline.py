import tempfile
import unittest
from pathlib import Path

from article_blueprint_os.config import load_journals
from article_blueprint_os.db import connect, init_db
from article_blueprint_os.pipeline import build_query, enumerate_journal
from article_blueprint_os.pubmed import FetchBatch, SearchHistory, parse_pubmed_xml


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "pubmed_sample.xml"


class FakeClient:
    def __init__(self):
        self.articles = parse_pubmed_xml(FIXTURE.read_bytes())[:1]

    def search_history(self, query):
        return SearchHistory(count=1, query_key="1", webenv="test")

    def fetch_history(self, history, *, batch_size=200):
        yield FetchBatch(
            retstart=0,
            articles=tuple(self.articles),
            raw_xml=FIXTURE.read_bytes(),
            sha256="0" * 64,
        )


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.connection = connect(Path(self.tempdir.name) / "test.sqlite3")
        init_db(self.connection)
        self.registry = load_journals(ROOT / "config" / "journals.json")

    def tearDown(self):
        self.connection.close()
        self.tempdir.cleanup()

    def test_build_query_is_journal_first(self):
        journal = self.registry.by_key("cancer_cell")
        query = build_query(journal, "2023-01-01", "2026-09-02")
        self.assertIn('"Cancer cell"[jour]', query)
        self.assertNotIn("tumor", query.casefold())
        self.assertNotIn("omics", query.casefold())

    def test_enumeration_is_idempotent_across_runs(self):
        journal = self.registry.by_key("cancer_cell")
        for _ in range(2):
            result = enumerate_journal(
                self.connection,
                FakeClient(),
                self.registry,
                journal,
                start_date="2023-01-01",
                end_date="2026-09-02",
                raw_dir=Path(self.tempdir.name) / "raw",
            )
            self.assertEqual("complete", result["status"])
        self.assertEqual(1, self.connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0])
        self.assertEqual(2, self.connection.execute("SELECT COUNT(*) FROM enumeration_runs").fetchone()[0])
        self.assertEqual(2, self.connection.execute("SELECT COUNT(*) FROM enumeration_batches").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
