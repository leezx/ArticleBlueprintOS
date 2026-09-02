import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from article_blueprint_os.backfill import (
    backfill_summary,
    export_coverage_report,
    plan_date_slices,
    run_historical_backfill,
)
from article_blueprint_os.config import Journal, JournalRegistry
from article_blueprint_os.db import connect, init_db
from article_blueprint_os.pubmed import Article, FetchBatch, SearchHistory


class FakeBackfillClient:
    def __init__(self, *, fail_journal=None):
        self.fail_journal = fail_journal

    @staticmethod
    def _journal_key(query):
        return "journal_b" if "Journal B" in query else "journal_a"

    def search_history(self, query):
        is_2023 = '"2023-01-01"' in query and '"2023-12-31"' in query
        is_full = '"2023-01-01"' in query and '"2026-09-02"' in query
        count = 1 if is_2023 or is_full else 0
        return SearchHistory(count=count, query_key="1", webenv=query)

    def fetch_history(self, history, *, batch_size=200):
        key = self._journal_key(history.webenv)
        if key == self.fail_journal:
            raise RuntimeError("synthetic fetch failure")
        suffix = "2" if key == "journal_b" else "1"
        article = Article(
            pmid=f"9000000{suffix}",
            doi=None,
            source_journal_title="Journal B" if key == "journal_b" else "Journal A",
            publication_date="2023-06-01",
            publication_date_precision="day",
            publication_year=2023,
            title=f"Synthetic article {suffix}",
            abstract="Synthetic abstract",
            article_types=("Journal Article",),
            authors=(),
            mesh_terms=(),
        )
        yield FetchBatch(
            retstart=0,
            articles=(article,),
            raw_xml=f"<journal>{key}</journal>".encode(),
            sha256=suffix * 64,
        )


class PartitionPlanningClient:
    def search_history(self, query):
        dates = re.findall(r'"(\d{4}-\d{2}-\d{2})"', query)
        start = date.fromisoformat(dates[-2])
        end = date.fromisoformat(dates[-1])
        count = 15_000 if (end - start).days > 700 else 7_500
        return SearchHistory(count=count, query_key="1", webenv=query)


def registry():
    journals = (
        Journal("journal_a", "Journal A", "Journal A", "Gold", ("general",), 1.0),
        Journal("journal_b", "Journal B", "Journal B", "Silver", ("general",), 2.0),
    )
    return JournalRegistry("test-v1", "2026-09-02", journals)


class BackfillTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.connection = connect(self.root / "metadata.sqlite3")
        init_db(self.connection)

    def tearDown(self):
        self.connection.close()
        self.tempdir.cleanup()

    def run_backfill(self, client=None, resume_id=None):
        return run_historical_backfill(
            self.connection,
            client or FakeBackfillClient(),
            registry(),
            start_date="2023-01-01",
            end_date="2026-09-02",
            raw_dir=self.root / "raw",
            software_revision="test-sha",
            resume_id=resume_id,
        )

    def test_complete_backfill_and_annual_reconciliation(self):
        result = self.run_backfill()
        self.assertEqual("complete", result["status"])
        self.assertEqual(2, result["completed_journals"])
        self.assertEqual(2, result["unique_articles"])
        self.assertEqual(8, result["annual_checks"])
        self.assertEqual(0, result["annual_discrepancies"])
        self.assertEqual(2, result["full_window_checks"])
        self.assertEqual(0, result["full_window_discrepancies"])
        self.assertEqual(2, len(list((self.root / "raw").glob("*/batch_*.xml"))))

    def test_resume_skips_completed_journals(self):
        first = self.run_backfill()
        before = self.connection.execute("SELECT COUNT(*) FROM enumeration_runs").fetchone()[0]
        second = self.run_backfill(resume_id=first["backfill_id"])
        after = self.connection.execute("SELECT COUNT(*) FROM enumeration_runs").fetchone()[0]
        self.assertEqual(before, after)
        self.assertEqual("complete", second["status"])

    def test_failed_journal_can_be_retried_without_deleting_history(self):
        with self.assertRaisesRegex(RuntimeError, "1 journal"):
            self.run_backfill(FakeBackfillClient(fail_journal="journal_b"))
        backfill_id = self.connection.execute(
            "SELECT backfill_id FROM historical_backfills"
        ).fetchone()[0]
        failed = backfill_summary(self.connection, backfill_id)
        self.assertEqual("failed", failed["status"])
        self.assertEqual(1, failed["failed_journals"])
        completed = self.run_backfill(resume_id=backfill_id)
        self.assertEqual("complete", completed["status"])
        attempts = self.connection.execute(
            """
            SELECT attempt_count FROM historical_backfill_journals
            WHERE backfill_id=? AND journal_key='journal_b'
            """,
            (backfill_id,),
        ).fetchone()[0]
        self.assertEqual(2, attempts)

    def test_coverage_report_is_external_and_machine_readable(self):
        result = self.run_backfill()
        output = self.root / "result" / "coverage.json"
        export_coverage_report(self.connection, result["backfill_id"], output)
        payload = json.loads(output.read_text())
        self.assertEqual(2, len(payload["journals"]))
        self.assertEqual(8, len(payload["annual_coverage"]))
        self.assertEqual(2, len(payload["full_window_coverage"]))
        self.assertEqual(2, len(payload["slices"]))

    def test_large_query_is_partitioned_below_pubmed_limit(self):
        journal = registry().journals[0]
        slices = plan_date_slices(
            PartitionPlanningClient(),
            journal,
            start_date="2023-01-01",
            end_date="2026-09-02",
        )
        self.assertEqual(2, len(slices))
        self.assertEqual(15_000, sum(item.expected_count for item in slices))
        self.assertTrue(all(item.expected_count <= 9_999 for item in slices))


if __name__ == "__main__":
    unittest.main()
