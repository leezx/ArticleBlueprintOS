from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .db import require_outside_repo
from .pubmed import utc_now


ENUMS = {
    "disease": {"cancer", "non-cancer", "unclear"},
    "study": {"original research", "review", "commentary", "method", "unclear"},
    "primary_contribution": {
        "biological discovery",
        "clinical discovery",
        "computational method",
        "experimental mechanism",
        "resource/atlas",
        "other",
    },
    "data_modalities": {
        "scRNA",
        "bulk RNA",
        "spatial",
        "genomics",
        "epigenomics",
        "proteomics",
        "multiomics",
        "pathology",
        "other",
    },
    "new_experimental_data": {"none", "limited", "substantial", "unclear"},
    "public_data_reuse": {"none", "minor", "major", "unclear"},
    "relevance": {"YES", "MAYBE", "NO"},
}


REQUIRED_FIELDS = {
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
    "model",
    "prompt_version",
    "screened_at",
}


def validate_llm_record(record: dict[str, Any]) -> None:
    missing = REQUIRED_FIELDS - record.keys()
    extra = record.keys() - REQUIRED_FIELDS
    if missing or extra:
        raise ValueError(f"Invalid fields; missing={sorted(missing)}, extra={sorted(extra)}")
    for field in ("disease", "study", "primary_contribution", "new_experimental_data", "public_data_reuse", "relevance"):
        if record[field] not in ENUMS[field]:
            raise ValueError(f"Invalid {field}: {record[field]!r}")
    modalities = record["data_modalities"]
    if not isinstance(modalities, list) or not modalities or len(modalities) != len(set(modalities)):
        raise ValueError("data_modalities must be a non-empty unique list")
    if set(modalities) - ENUMS["data_modalities"]:
        raise ValueError(f"Invalid data modality: {set(modalities) - ENUMS['data_modalities']}")
    centrality = record["computational_centrality"]
    if not isinstance(centrality, int) or isinstance(centrality, bool) or not 0 <= centrality <= 3:
        raise ValueError("computational_centrality must be an integer from 0 to 3")
    confidence = record["confidence"]
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
        raise ValueError("confidence must be from 0 to 1")
    for field in ("pmid", "rationale", "model", "prompt_version", "screened_at"):
        if not isinstance(record[field], str) or not record[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if not record["pmid"].isdigit():
        raise ValueError("pmid must contain only digits")
    try:
        datetime.fromisoformat(record["screened_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("screened_at must be an ISO date-time") from exc


def export_llm_queue(connection: sqlite3.Connection, path: str | Path) -> int:
    output = require_outside_repo(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = connection.execute(
        """
        WITH latest_rules AS (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY pmid ORDER BY screened_at DESC, rules_version DESC
            ) AS rn
            FROM deterministic_screens
        )
        SELECT a.pmid, a.doi, a.journal_key, a.publication_date, a.title,
               a.abstract, a.article_types_json, a.mesh_terms_json,
               COALESCE(ds.candidate_priority, 0) AS candidate_priority
        FROM articles a
        LEFT JOIN latest_rules ds ON ds.pmid = a.pmid AND ds.rn = 1
        ORDER BY candidate_priority DESC, a.publication_date DESC, a.pmid DESC
        """
    ).fetchall()
    with output.open("w", encoding="utf-8") as handle:
        for row in rows:
            payload = dict(row)
            payload["article_types"] = json.loads(payload.pop("article_types_json"))
            payload["mesh_terms"] = json.loads(payload.pop("mesh_terms_json"))
            payload["candidate_priority"] = bool(payload["candidate_priority"])
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    return len(rows)


def import_llm_results(connection: sqlite3.Connection, path: str | Path) -> int:
    records: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                validate_llm_record(record)
            except (json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"Invalid LLM result at line {line_number}: {exc}") from exc
            records.append(record)
    imported_at = utc_now()
    with connection:
        for record in records:
            exists = connection.execute(
                "SELECT 1 FROM articles WHERE pmid=?", (record["pmid"],)
            ).fetchone()
            if exists is None:
                raise ValueError(f"Unknown PMID in LLM results: {record['pmid']}")
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
                    record["pmid"], record["disease"], record["study"],
                    record["primary_contribution"],
                    json.dumps(record["data_modalities"], ensure_ascii=False),
                    record["computational_centrality"],
                    record["new_experimental_data"], record["public_data_reuse"],
                    record["relevance"], record["confidence"], record["rationale"],
                    record["model"], record["prompt_version"], record["screened_at"],
                    imported_at,
                ),
            )
    return len(records)


def sample_no_audit(
    connection: sqlite3.Connection,
    *,
    fraction: float = 0.10,
    seed: str = "article-blueprint-os-v1",
) -> dict[str, Any]:
    if not 0 < fraction <= 1:
        raise ValueError("fraction must be greater than 0 and at most 1")
    no_rows = connection.execute(
        """
        WITH ranked AS (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY pmid ORDER BY imported_at DESC, id DESC
            ) AS rn
            FROM llm_screens
        )
        SELECT pmid FROM ranked WHERE rn=1 AND relevance='NO'
        """
    ).fetchall()
    ranked = sorted(
        ((hashlib.sha256(f"{seed}:{row['pmid']}".encode()).hexdigest(), row["pmid"]) for row in no_rows)
    )
    sample_size = math.ceil(len(ranked) * fraction)
    selected = ranked[:sample_size]
    sample_id = str(uuid.uuid4())
    sampled_at = utc_now()
    with connection:
        for hash_rank, pmid in selected:
            connection.execute(
                """
                INSERT INTO audit_samples(
                    sample_id, pmid, source_relevance, fraction, seed,
                    hash_rank, sampled_at
                ) VALUES (?, ?, 'NO', ?, ?, ?, ?)
                """,
                (sample_id, pmid, fraction, seed, hash_rank, sampled_at),
            )
    return {
        "sample_id": sample_id,
        "population": len(ranked),
        "sample_size": sample_size,
        "fraction": fraction,
        "seed": seed,
    }
