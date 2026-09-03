import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from article_blueprint_os.db import connect, init_db
from article_blueprint_os.manual_web import (
    MODEL_VISIBLE_FIELDS,
    SEMANTIC_FIELDS,
    prepare_web_batches,
    validate_web_output,
)


def semantic(pmid: str) -> dict:
    return {
        "pmid": pmid,
        "disease": "cancer",
        "study": "original research",
        "primary_contribution": "biological discovery",
        "data_modalities": ["genomics"],
        "computational_centrality": 3,
        "new_experimental_data": "none",
        "public_data_reuse": "major",
        "relevance": "YES",
        "confidence": 0.9,
        "rationale": "Synthetic metadata supports scope.",
    }


class ManualWebTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "db.sqlite3"
        self.connection = connect(self.db)
        init_db(self.connection)
        self.connection.execute("PRAGMA foreign_keys=OFF")
        self.calibration_id = "calibration-test"
        self.connection.execute(
            "INSERT INTO calibration_samples VALUES (?, 'seed', 'v1', 'now')",
            (self.calibration_id,),
        )
        strata = (
            ("candidate_priority", 300),
            ("non_priority_original_or_unclear", 200),
            ("obvious_non_original", 100),
        )
        index = 0
        for stratum, count in strata:
            for _ in range(count):
                pmid = str(70_000_000 + index)
                index += 1
                self.connection.execute(
                    """
                    INSERT INTO articles(
                        pmid, journal_key, source_journal_title,
                        publication_date_precision, title, abstract,
                        article_types_json, authors_json, mesh_terms_json,
                        pubmed_url, first_seen_run_id, last_seen_run_id,
                        source_updated_at
                    ) VALUES (?, 'j', 'J', 'year', 'Synthetic title',
                              'Synthetic abstract', '["Journal Article"]',
                              '[]', '[]', 'u', 'r', 'r', 'x')
                    """,
                    (pmid,),
                )
                self.connection.execute(
                    "INSERT INTO calibration_sample_items VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        self.calibration_id,
                        pmid,
                        stratum,
                        count,
                        f"{index:08d}",
                        "now",
                    ),
                )
        self.connection.commit()
        self.output_root = self.root / "packets"

    def tearDown(self) -> None:
        self.connection.close()
        self.temp.cleanup()

    def packets(self, size: int = 20) -> list[dict]:
        return prepare_web_batches(
            self.connection,
            self.calibration_id,
            self.output_root,
            batch_size=size,
            software_revision="sha",
        )

    def manifest_path(self, manifest: dict) -> Path:
        return self.output_root / manifest["batch_id"] / "manifest.json"

    def write_output(self, manifest_path: Path, records: list[dict], name="output_raw.txt") -> Path:
        path = manifest_path.parent / name
        path.write_text("\n".join(json.dumps(record) for record in records) + "\n")
        return path

    def valid_output(self, manifest_path: Path, name="output_raw.txt") -> Path:
        manifest = json.loads(manifest_path.read_text())
        return self.write_output(
            manifest_path,
            [semantic(pmid) for pmid in manifest["ordered_pmids"]],
            name,
        )

    def validate(self, manifest_path: Path, output: Path, attempt=1):
        return validate_web_output(
            self.connection,
            manifest_path,
            output,
            model_display_name="Visible Model",
            operator="human",
            fresh_chat_confirmed=True,
            executed_at="2026-09-03T12:00:00Z",
            attempt=attempt,
        )

    def test_600_records_make_30_batches_and_are_reproducible(self) -> None:
        first = self.packets()
        second = self.packets()
        self.assertEqual(30, len(first))
        self.assertEqual(
            [item["batch_id"] for item in first],
            [item["batch_id"] for item in second],
        )
        self.assertEqual(
            [item["ordered_pmids"] for item in first],
            [item["ordered_pmids"] for item in second],
        )
        self.assertEqual(
            30,
            self.connection.execute(
                "SELECT COUNT(*) FROM manual_web_attempts"
            ).fetchone()[0],
        )

    def test_model_visible_packet_excludes_sampling_metadata(self) -> None:
        manifest = self.packets()[0]
        input_text = (self.output_root / manifest["batch_id"] / "input.jsonl").read_text()
        prompt_text = (
            self.output_root / manifest["batch_id"] / "web_prompt.txt"
        ).read_text()
        records = [json.loads(line) for line in input_text.splitlines()]
        self.assertEqual(20, len(records))
        for record in records:
            self.assertEqual(MODEL_VISIBLE_FIELDS, frozenset(record))
            self.assertNotIn("stratum", record)
            self.assertNotIn("candidate_priority", record)
            self.assertNotIn("population_size", record)
            self.assertNotIn("hash_rank", record)
            self.assertNotIn("journal_key", record)
            self.assertNotIn("publication_date", record)

        self.assertIn("sampling_strata", manifest)
        for forbidden in (
            '"stratum"',
            "candidate_priority",
            "non_priority_original_or_unclear",
            "obvious_non_original",
            "population_size",
            "hash_rank",
        ):
            self.assertNotIn(forbidden, input_text)
            self.assertNotIn(forbidden, prompt_text)

    def test_locked_sample_shape_and_batch_limit_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 1 and 50"):
            self.packets(51)
        self.assertEqual(12, len(self.packets(50)))
        with self.assertRaisesRegex(ValueError, "software_revision"):
            prepare_web_batches(
                self.connection,
                self.calibration_id,
                self.output_root,
                software_revision="unknown",
            )
        self.connection.execute(
            "DELETE FROM calibration_sample_items WHERE pmid='70000599'"
        )
        self.connection.commit()
        with self.assertRaisesRegex(ValueError, "exactly 600"):
            self.packets()

    def test_repo_payload_paths_fail(self) -> None:
        repo_payload = Path(__file__).parents[1] / "payload"
        with self.assertRaisesRegex(ValueError, "outside"):
            prepare_web_batches(
                self.connection,
                self.calibration_id,
                repo_payload,
                software_revision="sha",
            )

        manifest = self.packets()[0]
        with self.assertRaisesRegex(ValueError, "outside"):
            self.validate(self.manifest_path(manifest), Path(__file__))

    def test_output_must_match_its_batch_directory(self) -> None:
        manifest = self.packets()[0]
        manifest_path = self.manifest_path(manifest)
        other = self.root / "other-output.txt"
        other.write_text("synthetic")
        with self.assertRaisesRegex(ValueError, "batch directory"):
            self.validate(manifest_path, other)

    def test_valid_output_imports_and_records_operator_provenance(self) -> None:
        manifest = self.packets()[0]
        manifest_path = self.manifest_path(manifest)
        before = self.connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        rows = self.validate(manifest_path, self.valid_output(manifest_path))
        self.assertEqual(20, len(rows))
        self.assertEqual("Visible Model", rows[0]["model"])
        self.assertEqual("2026-09-03T12:00:00Z", rows[0]["screened_at"])
        self.assertEqual(
            20,
            self.connection.execute("SELECT COUNT(*) FROM llm_screens").fetchone()[0],
        )
        self.assertEqual(
            20,
            self.connection.execute(
                """
                SELECT COUNT(*) FROM manual_web_attempt_items
                WHERE batch_id=? AND attempt=1 AND llm_screen_id IS NOT NULL
                """,
                (manifest["batch_id"],),
            ).fetchone()[0],
        )
        self.assertEqual(
            before,
            self.connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0],
        )
        attempt = self.connection.execute(
            "SELECT * FROM manual_web_attempts WHERE batch_id=? AND attempt=1",
            (manifest["batch_id"],),
        ).fetchone()
        self.assertEqual("ChatGPT Web UI", attempt["provider_route"])
        self.assertEqual("manual", attempt["execution_mode"])
        self.assertEqual("Visible Model", attempt["model_display_name"])
        self.assertEqual("human", attempt["operator"])
        self.assertEqual(1, attempt["fresh_chat_confirmed"])
        self.assertEqual("2026-09-03T12:00:00Z", attempt["executed_at"])
        self.assertEqual("unavailable_not_exposed_by_ui", attempt["temperature"])

    def test_fresh_chat_and_visible_identity_are_required_and_audited(self) -> None:
        manifest = self.packets()[0]
        manifest_path = self.manifest_path(manifest)
        combinations = (
            ("", "human", True, "2026-09-03T12:00:00Z"),
            ("M", "", True, "2026-09-03T12:00:00Z"),
            ("M", "human", False, "2026-09-03T12:00:00Z"),
            ("M", "human", True, "not-a-date"),
        )
        for attempt, (model, operator, fresh, executed_at) in enumerate(
            combinations, start=1
        ):
            with self.assertRaises(ValueError):
                validate_web_output(
                    self.connection,
                    manifest_path,
                    self.valid_output(manifest_path, f"identity-{attempt}.txt"),
                    model_display_name=model,
                    operator=operator,
                    fresh_chat_confirmed=fresh,
                    executed_at=executed_at,
                    attempt=attempt,
                )
        self.assertEqual(
            4,
            self.connection.execute(
                "SELECT COUNT(*) FROM manual_web_attempts WHERE status='failed'"
            ).fetchone()[0],
        )

    def test_invalid_outputs_fail_and_are_audited(self) -> None:
        manifest = self.packets()[0]
        manifest_path = self.manifest_path(manifest)
        base = [semantic(pmid) for pmid in manifest["ordered_pmids"]]
        duplicate = [base[0], base[0], *base[2:]]
        unexpected = [*base]
        unexpected[5] = semantic("999")
        invalid_schema = [{**record, "confidence": 2} for record in base]
        extra_field = [{**record, "model": "forbidden"} for record in base]
        variants = (
            base[:-1],
            base + [semantic("999")],
            duplicate,
            unexpected,
            list(reversed(base)),
            invalid_schema,
            extra_field,
        )
        for attempt, records in enumerate(variants, start=1):
            path = self.write_output(manifest_path, records, f"bad-{attempt}.txt")
            with self.assertRaises(ValueError):
                self.validate(manifest_path, path, attempt=attempt)

        bad_json = manifest_path.parent / "bad-json.txt"
        bad_json.write_text("```json\n" + "\n".join("{}" for _ in range(19)))
        with self.assertRaises(ValueError):
            self.validate(manifest_path, bad_json, attempt=8)
        prose = manifest_path.parent / "bad-prose.txt"
        prose.write_text("Here are the results:\n" + "\n".join("{}" for _ in range(19)))
        with self.assertRaises(ValueError):
            self.validate(manifest_path, prose, attempt=9)
        self.assertEqual(
            9,
            self.connection.execute(
                "SELECT COUNT(*) FROM manual_web_attempts WHERE status='failed'"
            ).fetchone()[0],
        )

    def test_retry_preserves_first_attempt_and_raw_checksum(self) -> None:
        manifest = self.packets()[0]
        manifest_path = self.manifest_path(manifest)
        bad = manifest_path.parent / "bad.txt"
        bad.write_text("no")
        with self.assertRaises(ValueError):
            self.validate(manifest_path, bad)
        first_checksum = self.connection.execute(
            "SELECT output_sha256 FROM manual_web_attempts WHERE batch_id=? AND attempt=1",
            (manifest["batch_id"],),
        ).fetchone()[0]
        with self.assertRaisesRegex(ValueError, "next attempt must be 2"):
            self.validate(manifest_path, bad)
        self.validate(
            manifest_path,
            self.valid_output(manifest_path, "retry-2.txt"),
            attempt=2,
        )
        attempts = self.connection.execute(
            """
            SELECT attempt, status, output_sha256
            FROM manual_web_attempts WHERE batch_id=? ORDER BY attempt
            """,
            (manifest["batch_id"],),
        ).fetchall()
        self.assertEqual([(1, "failed"), (2, "valid")], [(x[0], x[1]) for x in attempts])
        self.assertEqual(first_checksum, attempts[0][2])

    def test_attempts_must_start_at_one_and_remain_consecutive(self) -> None:
        manifest = self.packets()[0]
        manifest_path = self.manifest_path(manifest)
        with self.assertRaisesRegex(ValueError, "next attempt must be 1"):
            self.validate(
                manifest_path,
                self.valid_output(manifest_path, "skip-first.txt"),
                attempt=2,
            )
        first = manifest_path.parent / "first-failed.txt"
        first.write_text("bad")
        with self.assertRaises(ValueError):
            self.validate(manifest_path, first, attempt=1)
        with self.assertRaisesRegex(ValueError, "next attempt must be 2"):
            self.validate(
                manifest_path,
                self.valid_output(manifest_path, "skip-second.txt"),
                attempt=3,
            )

    def test_import_failure_cannot_leave_attempt_valid(self) -> None:
        manifest = self.packets()[0]
        manifest_path = self.manifest_path(manifest)
        with patch(
            "article_blueprint_os.manual_web._import_records",
            side_effect=RuntimeError("synthetic write failure"),
        ):
            with self.assertRaisesRegex(ValueError, "record import failed"):
                self.validate(manifest_path, self.valid_output(manifest_path))
        self.assertEqual(
            "failed",
            self.connection.execute(
                "SELECT status FROM manual_web_attempts WHERE batch_id=? AND attempt=1",
                (manifest["batch_id"],),
            ).fetchone()[0],
        )
        self.assertEqual(
            0,
            self.connection.execute("SELECT COUNT(*) FROM llm_screens").fetchone()[0],
        )

    def test_changed_prior_raw_output_blocks_retry(self) -> None:
        manifest = self.packets()[0]
        manifest_path = self.manifest_path(manifest)
        first = manifest_path.parent / "first.txt"
        first.write_text("bad")
        with self.assertRaises(ValueError):
            self.validate(manifest_path, first)
        first.write_text("silently changed")
        second = self.valid_output(manifest_path, "second.txt")
        with self.assertRaisesRegex(ValueError, "missing or changed"):
            self.validate(manifest_path, second, attempt=2)

    def test_manifest_contract_and_input_checksum_fail_closed(self) -> None:
        manifest = self.packets()[0]
        manifest_path = self.manifest_path(manifest)
        output = self.valid_output(manifest_path)
        changed = json.loads(manifest_path.read_text())
        changed["schema_version"] = "wrong"
        manifest_path.write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError, "schema version"):
            self.validate(manifest_path, output)

        manifest_path.write_text(json.dumps(manifest))
        prompt_path = manifest_path.parent / "web_prompt.txt"
        original_prompt = prompt_path.read_text()
        prompt_path.write_text("changed")
        with self.assertRaisesRegex(ValueError, "prompt checksum"):
            self.validate(manifest_path, output)
        prompt_path.write_text(original_prompt)

        self.connection.execute(
            "UPDATE calibration_samples SET prompt_version='v2' WHERE calibration_id=?",
            (self.calibration_id,),
        )
        self.connection.commit()
        with self.assertRaisesRegex(ValueError, "prompt version"):
            self.validate(manifest_path, output)

        self.connection.execute(
            "UPDATE calibration_samples SET prompt_version='v1' WHERE calibration_id=?",
            (self.calibration_id,),
        )
        self.connection.commit()
        (manifest_path.parent / "input.jsonl").write_text("changed")
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.validate(manifest_path, output)

    def test_semantic_schema_and_prompt_are_explicit_and_complete(self) -> None:
        schema = json.loads(
            (Path(__file__).parents[1] / "schemas/web_semantic_screen_v1.schema.json").read_text()
        )
        self.assertEqual(SEMANTIC_FIELDS, frozenset(schema["required"]))
        self.assertEqual(SEMANTIC_FIELDS, frozenset(schema["properties"]))
        manifest = self.packets()[0]
        prompt = (self.output_root / manifest["batch_id"] / "web_prompt.txt").read_text()
        self.assertIn("Prefer `MAYBE` over `NO`", prompt)
        self.assertIn("AIDD", prompt)
        self.assertIn("same order", prompt)
        self.assertIn('"resource/atlas"', prompt)
        self.assertIn('"multiomics"', prompt)
        self.assertNotIn("Use prompt version `v1`", prompt)

    def test_module_has_no_network_or_browser_automation(self) -> None:
        source = (
            Path(__file__).parents[1] / "src/article_blueprint_os/manual_web.py"
        ).read_text()
        for forbidden in ("urllib", "requests", "playwright", "selenium"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
