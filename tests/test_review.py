import tempfile
import unittest
from pathlib import Path

from article_blueprint_os.db import connect, init_db
from article_blueprint_os.review import calibration_stratum, create_calibration_sample, sample_no_audit, validate_llm_record


def valid_record(pmid="40000001", relevance="YES"):
    return {
        "pmid": pmid,
        "disease": "cancer",
        "study": "original research",
        "primary_contribution": "biological discovery",
        "data_modalities": ["scRNA", "spatial"],
        "computational_centrality": 3,
        "new_experimental_data": "limited",
        "public_data_reuse": "major",
        "relevance": relevance,
        "confidence": 0.9,
        "rationale": "Computational integration carries the claim.",
        "model": "test-model",
        "prompt_version": "v1",
        "screened_at": "2026-09-02T12:00:00Z",
    }


class ReviewTests(unittest.TestCase):
    def test_validate_record(self):
        validate_llm_record(valid_record())

    def test_invalid_enum_fails(self):
        record = valid_record()
        record["relevance"] = "PROBABLY"
        with self.assertRaisesRegex(ValueError, "Invalid relevance"):
            validate_llm_record(record)

    def test_seeded_no_sample_uses_exact_ceiling(self):
        with tempfile.TemporaryDirectory() as tempdir:
            connection = connect(Path(tempdir) / "test.sqlite3")
            init_db(connection)
            connection.execute("PRAGMA foreign_keys = OFF")
            for index in range(21):
                pmid = str(50000000 + index)
                connection.execute(
                    """
                    INSERT INTO llm_screens(
                        pmid,disease,study,primary_contribution,data_modalities_json,
                        computational_centrality,new_experimental_data,public_data_reuse,
                        relevance,confidence,rationale,model,prompt_version,screened_at,imported_at
                    ) VALUES (?, 'cancer', 'original research', 'other', '[\"other\"]',
                              2, 'none', 'major', 'NO', 0.8, 'x', 'm', 'v1',
                              '2026-09-02T00:00:00Z', '2026-09-02T00:00:01Z')
                    """,
                    (pmid,),
                )
            connection.commit()
            result = sample_no_audit(connection, fraction=0.10, seed="locked")
            self.assertEqual(21, result["population"])
            self.assertEqual(3, result["sample_size"])
            connection.close()

    def test_calibration_sample_is_stratified_and_reproducible(self):
        with tempfile.TemporaryDirectory() as tempdir:
            connection = connect(Path(tempdir) / "test.sqlite3")
            init_db(connection)
            connection.execute("PRAGMA foreign_keys = OFF")
            for index in range(650):
                pmid = str(60000000 + index)
                priority = 1 if index < 310 else 0
                types = '["Review"]' if index >= 510 else '["Journal Article"]'
                connection.execute("INSERT INTO articles(pmid,journal_key,source_journal_title,publication_date_precision,title,abstract,article_types_json,authors_json,mesh_terms_json,pubmed_url,first_seen_run_id,last_seen_run_id,source_updated_at) VALUES (?, 'j','J','year','t','a',?, '[]','[]','u','r','r','x')", (pmid, types))
                connection.execute("INSERT INTO deterministic_screens(pmid,rules_version,cancer_hit,omics_hit,candidate_priority,cancer_terms_json,omics_terms_json,screened_at) VALUES (?, 'v1',1,1,?,'[]','[]','x')", (pmid, priority))
            connection.commit()
            result = create_calibration_sample(connection, seed="locked")
            self.assertEqual(300, result["strata"]["candidate_priority"]["selected"])
            self.assertEqual(200, result["strata"]["non_priority_original_or_unclear"]["selected"])
            self.assertEqual(100, result["strata"]["obvious_non_original"]["selected"])
            self.assertEqual(600, connection.execute("SELECT COUNT(*) FROM calibration_sample_items").fetchone()[0])
            first = connection.execute("SELECT stratum, pmid, hash_rank FROM calibration_sample_items WHERE calibration_id=? ORDER BY stratum, hash_rank", (result["calibration_id"],)).fetchall()
            repeat = create_calibration_sample(connection, seed="locked")
            second = connection.execute("SELECT stratum, pmid, hash_rank FROM calibration_sample_items WHERE calibration_id=? ORDER BY stratum, hash_rank", (repeat["calibration_id"],)).fetchall()
            self.assertEqual([tuple(row) for row in first], [tuple(row) for row in second])
            connection.close()

    def test_calibration_stratum_uses_screening_non_original_types(self):
        self.assertEqual("obvious_non_original", calibration_stratum(candidate_priority=False, article_types=["Systematic Review"]))
        self.assertEqual("non_priority_original_or_unclear", calibration_stratum(candidate_priority=False, article_types=["Journal Article"]))
        self.assertEqual("non_priority_original_or_unclear", calibration_stratum(candidate_priority=False, article_types=[]))
        self.assertIsNone(calibration_stratum(candidate_priority=False, article_types=["Randomized Controlled Trial"]))


if __name__ == "__main__":
    unittest.main()
