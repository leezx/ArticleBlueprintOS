"""Manual-only ChatGPT Web calibration bridge. Contains no network code."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .db import REPO_ROOT, require_outside_repo
from .review import validate_llm_record


WEB_SEMANTIC_SCHEMA_VERSION = "web-semantic-v1"
SEMANTIC_FIELDS = frozenset(
    {
        "pmid",
        "disease",
        "study",
        "primary_contribution",
        "data_modalities",
        "computational_centrality",
        "new_experimental_data",
        "public_data_reuse",
        "relevance",
        "confidence",
        "rationale",
    }
)
LOCKED_STRATA = {
    "candidate_priority": 300,
    "non_priority_original_or_unclear": 200,
    "obvious_non_original": 100,
}
MODEL_VISIBLE_FIELDS = frozenset(
    {"pmid", "doi", "title", "abstract", "article_types", "mesh_terms"}
)
UNAVAILABLE = "unavailable_not_exposed_by_ui"
AUTOMATED_WRAPPER_VERSION = "ABOS-WEB-WRAPPER-v1"
AUTOMATED_WRAPPER_TEXT = "ABOS-WEB-WRAPPER-v1: Execute the attached web_prompt.txt exactly."


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def batch_id(calibration_id: str, pmids: list[str], prompt_version: str) -> str:
    payload = "\n".join((calibration_id, prompt_version, *pmids))
    return hashlib.sha256(payload.encode()).hexdigest()[:24]


def _web_prompt(input_text: str) -> str:
    """Embed the complete reviewed v1 semantics while excluding provenance."""
    prompt = (REPO_ROOT / "prompts" / "llm_screen_v1.md").read_text()
    semantic_schema = (
        REPO_ROOT / "schemas" / "web_semantic_screen_v1.schema.json"
    ).read_text()
    prompt = prompt.replace(
        "The object must validate against\n`schemas/llm_screen.schema.json`.",
        "The object must validate against "
        "`schemas/web_semantic_screen_v1.schema.json`.",
    )
    prompt = prompt.replace(
        "- `model`, `prompt_version`, and `screened_at`: provenance fields supplied by\n"
        "  the calling workflow. Use prompt version `v1`.",
        "- Do not return `model`, `prompt_version`, or `screened_at`; trusted local "
        "software supplies them after validation.",
    )
    return (
        prompt
        + "\n\nProcess only the supplied metadata. Return exactly one object for every "
        "input PMID, in the same order, as JSONL only. Do not browse. Do not add "
        "markdown fences, prose, omissions, additions, or guessed provenance.\n\n"
        "STAGE-A JSON SCHEMA\n"
        + semantic_schema
        + "\n\n"
        "INPUT JSONL\n"
        + input_text
    )


def _validate_locked_sample(items: list[sqlite3.Row]) -> None:
    observed = {
        key: sum(row["stratum"] == key for row in items) for key in LOCKED_STRATA
    }
    if len(items) != 600 or observed != LOCKED_STRATA:
        raise ValueError(
            "calibration sample must be exactly 600 records in locked "
            "300/200/100 strata"
        )


def _model_visible_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "pmid": row["pmid"],
        "doi": row["doi"],
        "title": row["title"],
        "abstract": row["abstract"],
        "article_types": json.loads(row["article_types_json"]),
        "mesh_terms": json.loads(row["mesh_terms_json"]),
    }


def prepare_web_batches(
    connection: sqlite3.Connection,
    calibration_id: str,
    root: str | Path,
    *,
    batch_size: int = 20,
    software_revision: str,
) -> list[dict[str, Any]]:
    """Create deterministic external packets for manual Web execution."""
    if not 1 <= batch_size <= 50:
        raise ValueError("manual Web batch_size must be between 1 and 50")
    if not software_revision.strip() or software_revision == "unknown":
        raise ValueError("an exact software_revision is required")
    root = require_outside_repo(root)
    sample = connection.execute(
        "SELECT prompt_version FROM calibration_samples WHERE calibration_id=?",
        (calibration_id,),
    ).fetchone()
    if sample is None:
        raise ValueError("Unknown calibration_id")
    prompt_version = sample["prompt_version"]
    items = connection.execute(
        """
        SELECT i.pmid, i.stratum, a.doi, a.title, a.abstract,
               a.article_types_json, a.mesh_terms_json
        FROM calibration_sample_items i
        JOIN articles a ON a.pmid=i.pmid
        WHERE i.calibration_id=?
        ORDER BY i.stratum, i.hash_rank
        """,
        (calibration_id,),
    ).fetchall()
    _validate_locked_sample(items)

    packets: list[dict[str, Any]] = []
    for start in range(0, 600, batch_size):
        chunk = items[start : start + batch_size]
        pmids = [row["pmid"] for row in chunk]
        ident = batch_id(calibration_id, pmids, prompt_version)
        directory = root / ident
        directory.mkdir(parents=True, exist_ok=True)

        lines = []
        for row in chunk:
            payload = _model_visible_payload(row)
            lines.append(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        input_text = "\n".join(lines) + "\n"
        input_path = directory / "input.jsonl"
        if input_path.exists() and input_path.read_text() != input_text:
            raise ValueError("existing deterministic input mismatch")
        if not input_path.exists():
            input_path.write_text(input_text)
        prompt_text = _web_prompt(input_text)
        prompt_path = directory / "web_prompt.txt"
        if prompt_path.exists() and prompt_path.read_text() != prompt_text:
            raise ValueError("existing deterministic Web prompt mismatch")
        if not prompt_path.exists():
            prompt_path.write_text(prompt_text)

        created_at = _now()
        manifest = {
            "calibration_id": calibration_id,
            "batch_id": ident,
            "ordered_pmids": pmids,
            "record_count": len(pmids),
            "prompt_version": prompt_version,
            "schema_version": WEB_SEMANTIC_SCHEMA_VERSION,
            "sampling_strata": [row["stratum"] for row in chunk],
            "input_sha256": _sha(input_path),
            "web_prompt_sha256": _sha(prompt_path),
            "created_at": created_at,
            "software_revision": software_revision,
            "status": "prepared",
            "attempt": 1,
        }
        manifest_path = directory / "manifest.json"
        if manifest_path.exists():
            previous = json.loads(manifest_path.read_text())
            immutable_keys = (
                "calibration_id",
                "batch_id",
                "ordered_pmids",
                "record_count",
                "prompt_version",
                "schema_version",
                "sampling_strata",
                "input_sha256",
                "web_prompt_sha256",
                "software_revision",
            )
            if any(previous.get(key) != manifest[key] for key in immutable_keys):
                raise ValueError("existing deterministic manifest mismatch")
            manifest = previous
        else:
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n"
            )
        with connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO manual_web_attempts(
                    batch_id, attempt, calibration_id, provider_route,
                    execution_mode, model_identifier_precision, prompt_version,
                    software_revision, input_path, input_sha256, record_count,
                    fresh_chat_confirmed, temperature, maximum_output_tokens,
                    status, created_at
                ) VALUES (?, 1, ?, 'ChatGPT Web UI', 'manual',
                          'ui-display-name-only', ?, ?, ?, ?, ?, 0, ?, ?,
                          'prepared', ?)
                """,
                (
                    ident,
                    calibration_id,
                    prompt_version,
                    software_revision,
                    str(input_path),
                    manifest["input_sha256"],
                    len(pmids),
                    UNAVAILABLE,
                    UNAVAILABLE,
                    manifest["created_at"],
                ),
            )
            connection.executemany(
                """
                INSERT OR IGNORE INTO manual_web_attempt_items(
                    batch_id, attempt, pmid, ordinal
                ) VALUES (?, 1, ?, ?)
                """,
                [(ident, pmid, ordinal) for ordinal, pmid in enumerate(pmids, 1)],
            )
        packets.append(manifest)
    return packets


def _validate_manifest(manifest_path: Path, manifest: dict[str, Any]) -> Path:
    required = {
        "calibration_id",
        "batch_id",
        "ordered_pmids",
        "record_count",
        "prompt_version",
        "schema_version",
        "sampling_strata",
        "input_sha256",
        "web_prompt_sha256",
        "created_at",
        "software_revision",
    }
    if required - manifest.keys():
        raise ValueError("manifest is missing required fields")
    if manifest["schema_version"] != WEB_SEMANTIC_SCHEMA_VERSION:
        raise ValueError("wrong semantic schema version")
    if not isinstance(manifest["prompt_version"], str) or not manifest[
        "prompt_version"
    ].strip():
        raise ValueError("wrong prompt version")
    if manifest["record_count"] != len(manifest["ordered_pmids"]):
        raise ValueError("manifest record count mismatch")
    expected_id = batch_id(
        manifest["calibration_id"],
        manifest["ordered_pmids"],
        manifest["prompt_version"],
    )
    if manifest["batch_id"] != expected_id or manifest_path.parent.name != expected_id:
        raise ValueError("batch identity mismatch")
    input_path = require_outside_repo(manifest_path.parent / "input.jsonl")
    if _sha(input_path) != manifest["input_sha256"]:
        raise ValueError("input checksum mismatch")
    prompt_path = require_outside_repo(manifest_path.parent / "web_prompt.txt")
    if _sha(prompt_path) != manifest["web_prompt_sha256"]:
        raise ValueError("Web prompt checksum mismatch")
    return input_path


def _validate_manifest_against_db(
    connection: sqlite3.Connection, manifest: dict[str, Any]
) -> None:
    sample = connection.execute(
        "SELECT prompt_version FROM calibration_samples WHERE calibration_id=?",
        (manifest["calibration_id"],),
    ).fetchone()
    if sample is None or sample["prompt_version"] != manifest["prompt_version"]:
        raise ValueError("wrong prompt version")
    items = connection.execute(
        """
        SELECT pmid, stratum
        FROM calibration_sample_items
        WHERE calibration_id=?
        ORDER BY stratum, hash_rank
        """,
        (manifest["calibration_id"],),
    ).fetchall()
    _validate_locked_sample(items)
    expected_pmids = [row["pmid"] for row in items]
    ordered_pmids = manifest["ordered_pmids"]
    if not 1 <= len(ordered_pmids) <= 50:
        raise ValueError("manual Web manifests must contain between 1 and 50 records")
    try:
        start = expected_pmids.index(ordered_pmids[0])
    except (ValueError, IndexError) as exc:
        raise ValueError("manifest contains an unknown calibration PMID") from exc
    expected_chunk = items[start : start + len(ordered_pmids)]
    if [row["pmid"] for row in expected_chunk] != ordered_pmids:
        raise ValueError("manifest PMIDs are not a contiguous ordered sample batch")
    if [row["stratum"] for row in expected_chunk] != manifest["sampling_strata"]:
        raise ValueError("manifest sampling strata mismatch")


def _validate_semantic_record(record: Any, line_number: int) -> dict[str, Any]:
    """Validate Stage A without accepting model-supplied provenance fields."""
    if not isinstance(record, dict) or set(record) != SEMANTIC_FIELDS:
        raise ValueError(f"missing or extra semantic fields at line {line_number}")
    candidate = dict(record)
    candidate.update(
        model="stage-a-local-validation",
        prompt_version="stage-a-local-validation",
        screened_at="1970-01-01T00:00:00Z",
    )
    validate_llm_record(candidate)
    return dict(record)


def _verify_prior_raw_outputs(
    connection: sqlite3.Connection, batch_ident: str, output_path: Path
) -> None:
    rows = connection.execute(
        """
        SELECT output_path, output_sha256
        FROM manual_web_attempts
        WHERE batch_id=? AND status IN ('valid', 'failed')
        """,
        (batch_ident,),
    ).fetchall()
    for row in rows:
        prior_path = Path(row["output_path"]).resolve()
        if prior_path == output_path:
            raise ValueError("retry must use a new raw output path")
        if not prior_path.is_file() or _sha(prior_path) != row["output_sha256"]:
            raise ValueError("prior raw output is missing or changed")


def _validate_attempt_sequence(
    connection: sqlite3.Connection, batch_ident: str, attempt: int
) -> None:
    rows = connection.execute(
        """
        SELECT attempt, status FROM manual_web_attempts
        WHERE batch_id=? ORDER BY attempt
        """,
        (batch_ident,),
    ).fetchall()
    completed = [row for row in rows if row["status"] in {"valid", "failed"}]
    if any(row["status"] == "valid" for row in completed):
        raise ValueError("a valid attempt already completed this batch")
    expected = len(completed) + 1
    if attempt != expected:
        raise ValueError(f"next attempt must be {expected}")
    if attempt > 1 and [row["attempt"] for row in completed] != list(range(1, attempt)):
        raise ValueError("prior attempts must be complete and strictly consecutive")


def _record_attempt(
    connection: sqlite3.Connection,
    manifest: dict[str, Any],
    *,
    attempt: int,
    model_display_name: str,
    operator: str,
    input_path: Path,
    output_path: Path,
    output_sha256: str,
    fresh_chat_confirmed: bool,
    executed_at: str,
    status: str,
    error: str | None,
    completed_at: str,
    execution_mode: str,
    wrapper_version: str | None = None,
    wrapper_sha256: str | None = None,
) -> None:
    existing = connection.execute(
        "SELECT status FROM manual_web_attempts WHERE batch_id=? AND attempt=?",
        (manifest["batch_id"], attempt),
    ).fetchone()
    if existing is not None and existing["status"] in {"valid", "failed"}:
        raise ValueError("attempt number already completed; use a new attempt")

    if existing is None:
        connection.execute(
            """
            INSERT INTO manual_web_attempts(
                batch_id, attempt, calibration_id, provider_route,
                execution_mode, model_display_name,
                model_identifier_precision, operator, prompt_version,
                software_revision, input_path, input_sha256, output_path,
                output_sha256, record_count, wrapper_version, wrapper_sha256,
                fresh_chat_confirmed,
                temperature, maximum_output_tokens, status, error,
                created_at, submitted_at, executed_at, completed_at
            ) VALUES (?, ?, ?, 'ChatGPT Web UI', ?, ?, 'ui-display-name-only',
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                manifest["batch_id"],
                attempt,
                manifest["calibration_id"],
                execution_mode,
                model_display_name,
                operator,
                manifest["prompt_version"],
                manifest["software_revision"],
                str(input_path),
                manifest["input_sha256"],
                str(output_path),
                output_sha256,
                manifest["record_count"],
                wrapper_version,
                wrapper_sha256,
                int(fresh_chat_confirmed),
                UNAVAILABLE,
                UNAVAILABLE,
                status,
                error,
                manifest["created_at"],
                executed_at,
                executed_at,
                completed_at,
            ),
        )
        connection.execute(
            "UPDATE manual_web_attempts SET wrapper_version=?, wrapper_sha256=? WHERE batch_id=? AND attempt=?",
            (wrapper_version, wrapper_sha256, manifest["batch_id"], attempt),
        )
        connection.executemany(
            """
            INSERT INTO manual_web_attempt_items(
                batch_id, attempt, pmid, ordinal
            ) VALUES (?, ?, ?, ?)
            """,
            [
                (manifest["batch_id"], attempt, pmid, ordinal)
                for ordinal, pmid in enumerate(manifest["ordered_pmids"], 1)
            ],
        )
    else:
        connection.execute(
            """
            UPDATE manual_web_attempts
            SET execution_mode=?, model_display_name=?, operator=?, output_path=?,
                output_sha256=?, fresh_chat_confirmed=?, status=?, error=?,
                submitted_at=?, executed_at=?, completed_at=?
            WHERE batch_id=? AND attempt=? AND status='prepared'
            """,
            (
                execution_mode,
                model_display_name,
                operator,
                str(output_path),
                output_sha256,
                int(fresh_chat_confirmed),
                status,
                error,
                executed_at,
                executed_at,
                completed_at,
                manifest["batch_id"],
                attempt,
            ),
        )
        connection.execute(
            "UPDATE manual_web_attempts SET wrapper_version=?, wrapper_sha256=? WHERE batch_id=? AND attempt=?",
            (wrapper_version, wrapper_sha256, manifest["batch_id"], attempt),
        )


def _import_records(
    connection: sqlite3.Connection,
    records: list[dict[str, Any]],
    *,
    batch_ident: str,
    attempt: int,
) -> None:
    imported_at = _now()
    for record in records:
        connection.execute(
            """
            INSERT OR IGNORE INTO llm_screens(
                pmid, disease, study, primary_contribution,
                data_modalities_json, computational_centrality,
                new_experimental_data, public_data_reuse, relevance,
                confidence, rationale, model, prompt_version, screened_at,
                imported_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["pmid"],
                record["disease"],
                record["study"],
                record["primary_contribution"],
                json.dumps(record["data_modalities"], ensure_ascii=False),
                record["computational_centrality"],
                record["new_experimental_data"],
                record["public_data_reuse"],
                record["relevance"],
                record["confidence"],
                record["rationale"],
                record["model"],
                record["prompt_version"],
                record["screened_at"],
                imported_at,
            ),
        )
        screen = connection.execute(
            """
            SELECT id FROM llm_screens
            WHERE pmid=? AND model=? AND prompt_version=? AND screened_at=?
            """,
            (
                record["pmid"],
                record["model"],
                record["prompt_version"],
                record["screened_at"],
            ),
        ).fetchone()
        connection.execute(
            """
            UPDATE manual_web_attempt_items SET llm_screen_id=?
            WHERE batch_id=? AND attempt=? AND pmid=?
            """,
            (screen["id"], batch_ident, attempt, record["pmid"]),
        )


def validate_web_output(
    connection: sqlite3.Connection,
    manifest_path: str | Path,
    output: str | Path,
    *,
    model_display_name: str,
    operator: str,
    fresh_chat_confirmed: bool,
    executed_at: str,
    attempt: int = 1,
    execution_mode: str = "manual",
) -> list[dict[str, Any]]:
    """Validate immutable raw Web output, record the attempt, then import it."""
    manifest_path = require_outside_repo(manifest_path)
    output_path = require_outside_repo(output)
    if output_path.parent != manifest_path.parent:
        raise ValueError("raw output must stay in its external batch directory")
    manifest = json.loads(manifest_path.read_text())
    input_path = _validate_manifest(manifest_path, manifest)
    _validate_manifest_against_db(connection, manifest)
    if attempt < 1:
        raise ValueError("attempt must be at least 1")
    if execution_mode not in {"manual", "automated_browser"}:
        raise ValueError("execution_mode must be manual or automated_browser")
    wrapper_version = None
    wrapper_sha256 = None
    if execution_mode == "automated_browser":
        wrapper_version = AUTOMATED_WRAPPER_VERSION
        wrapper_sha256 = hashlib.sha256(AUTOMATED_WRAPPER_TEXT.encode()).hexdigest()
    _validate_attempt_sequence(connection, manifest["batch_id"], attempt)
    existing = connection.execute(
        "SELECT status FROM manual_web_attempts WHERE batch_id=? AND attempt=?",
        (manifest["batch_id"], attempt),
    ).fetchone()
    if existing is not None and existing["status"] in {"valid", "failed"}:
        raise ValueError("attempt number already completed; use a new attempt")
    _verify_prior_raw_outputs(connection, manifest["batch_id"], output_path)

    raw_sha = _sha(output_path)
    records: list[dict[str, Any]] = []
    error: str | None = None
    try:
        if not model_display_name.strip() or not operator.strip():
            raise ValueError("model_display_name and operator are required")
        if not fresh_chat_confirmed:
            raise ValueError("fresh_chat_confirmed=true is required")
        if not isinstance(executed_at, str) or not executed_at.strip():
            raise ValueError("executed_at is required")
        try:
            datetime.fromisoformat(executed_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("executed_at must be an ISO date-time") from exc
        lines = output_path.read_text().splitlines()
        if len(lines) != manifest["record_count"]:
            raise ValueError("wrong record count")
        seen: set[str] = set()
        screened_at = executed_at
        for line_number, (line, pmid) in enumerate(
            zip(lines, manifest["ordered_pmids"]), start=1
        ):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid JSON, markdown, or extra prose at line {line_number}"
                ) from exc
            record = _validate_semantic_record(record, line_number)
            if record["pmid"] in seen:
                raise ValueError(f"duplicate PMID at line {line_number}")
            seen.add(record["pmid"])
            if record["pmid"] != pmid:
                raise ValueError(
                    f"missing, unexpected, or reordered PMID at line {line_number}"
                )
            record.update(
                model=model_display_name,
                prompt_version=manifest["prompt_version"],
                screened_at=screened_at,
            )
            validate_llm_record(record)
            records.append(record)
    except Exception as exc:
        error = str(exc)

    completed_at = _now()
    if error is None:
        try:
            with connection:
                _record_attempt(
                    connection,
                    manifest,
                    attempt=attempt,
                    model_display_name=model_display_name,
                    operator=operator,
                    input_path=input_path,
                    output_path=output_path,
                    output_sha256=raw_sha,
                    fresh_chat_confirmed=fresh_chat_confirmed,
                    executed_at=executed_at,
                    status="valid",
                    error=None,
                    completed_at=completed_at,
                    execution_mode=execution_mode,
                    wrapper_version=wrapper_version,
                    wrapper_sha256=wrapper_sha256,
                )
                _import_records(
                    connection,
                    records,
                    batch_ident=manifest["batch_id"],
                    attempt=attempt,
                )
        except Exception as exc:
            error = f"record import failed: {exc}"
    if error is not None:
        with connection:
            _record_attempt(
                connection,
                manifest,
                attempt=attempt,
                model_display_name=model_display_name,
                operator=operator,
                input_path=input_path,
                output_path=output_path,
                output_sha256=raw_sha,
                fresh_chat_confirmed=fresh_chat_confirmed,
                executed_at=executed_at,
                status="failed",
                error=error,
                completed_at=completed_at,
                execution_mode=execution_mode,
                wrapper_version=wrapper_version,
                wrapper_sha256=wrapper_sha256,
            )
    status = "failed" if error else "valid"
    report = {
        "batch_id": manifest["batch_id"],
        "attempt": attempt,
        "status": status,
        "output_sha256": raw_sha,
        "record_count": len(records),
        "error": error,
    }
    report_name = (
        "validation.json" if attempt == 1 else f"validation.attempt-{attempt}.json"
    )
    (manifest_path.parent / report_name).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    manifest["status"] = status
    manifest["attempt"] = attempt
    manifest["latest_attempt"] = attempt
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    if error:
        raise ValueError(error)

    return records
