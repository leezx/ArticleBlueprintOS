import tempfile
import unittest
from pathlib import Path

from article_blueprint_os.db import connect, init_db
from article_blueprint_os.review import sample_no_audit, validate_llm_record


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


if __name__ == "__main__":
    unittest.main()
