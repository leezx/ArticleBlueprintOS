from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


SCHEMA_VERSION = 1
REPO_ROOT = Path(__file__).resolve().parents[2]


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS enumeration_runs (
    run_id TEXT PRIMARY KEY,
    journal_key TEXT NOT NULL,
    journal_title TEXT NOT NULL,
    registry_version TEXT NOT NULL,
    query TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    expected_count INTEGER,
    fetched_count INTEGER NOT NULL DEFAULT 0,
    unique_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL CHECK (status IN ('running', 'complete', 'failed')),
    error TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS articles (
    pmid TEXT PRIMARY KEY,
    doi TEXT,
    journal_key TEXT NOT NULL,
    source_journal_title TEXT NOT NULL,
    publication_date TEXT,
    publication_date_precision TEXT NOT NULL,
    publication_year INTEGER,
    title TEXT NOT NULL,
    abstract TEXT NOT NULL,
    article_types_json TEXT NOT NULL,
    authors_json TEXT NOT NULL,
    mesh_terms_json TEXT NOT NULL,
    pubmed_url TEXT NOT NULL,
    first_seen_run_id TEXT NOT NULL REFERENCES enumeration_runs(run_id),
    last_seen_run_id TEXT NOT NULL REFERENCES enumeration_runs(run_id),
    source_updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS articles_doi
ON articles(doi) WHERE doi IS NOT NULL;
CREATE INDEX IF NOT EXISTS articles_journal_date
ON articles(journal_key, publication_date);

CREATE TABLE IF NOT EXISTS enumeration_membership (
    run_id TEXT NOT NULL REFERENCES enumeration_runs(run_id) ON DELETE CASCADE,
    pmid TEXT NOT NULL REFERENCES articles(pmid) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    PRIMARY KEY (run_id, pmid)
);

CREATE TABLE IF NOT EXISTS enumeration_batches (
    run_id TEXT NOT NULL REFERENCES enumeration_runs(run_id) ON DELETE CASCADE,
    retstart INTEGER NOT NULL,
    record_count INTEGER NOT NULL,
    raw_xml_path TEXT NOT NULL,
    byte_size INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    PRIMARY KEY (run_id, retstart)
);

CREATE TABLE IF NOT EXISTS deterministic_screens (
    pmid TEXT NOT NULL REFERENCES articles(pmid) ON DELETE CASCADE,
    rules_version TEXT NOT NULL,
    cancer_hit INTEGER NOT NULL CHECK (cancer_hit IN (0, 1)),
    omics_hit INTEGER NOT NULL CHECK (omics_hit IN (0, 1)),
    candidate_priority INTEGER NOT NULL CHECK (candidate_priority IN (0, 1)),
    cancer_terms_json TEXT NOT NULL,
    omics_terms_json TEXT NOT NULL,
    screened_at TEXT NOT NULL,
    PRIMARY KEY (pmid, rules_version)
);

CREATE TABLE IF NOT EXISTS llm_screens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pmid TEXT NOT NULL REFERENCES articles(pmid) ON DELETE CASCADE,
    disease TEXT NOT NULL,
    study TEXT NOT NULL,
    primary_contribution TEXT NOT NULL,
    data_modalities_json TEXT NOT NULL,
    computational_centrality INTEGER NOT NULL CHECK (computational_centrality BETWEEN 0 AND 3),
    new_experimental_data TEXT NOT NULL,
    public_data_reuse TEXT NOT NULL,
    relevance TEXT NOT NULL CHECK (relevance IN ('YES', 'MAYBE', 'NO')),
    confidence REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    rationale TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    screened_at TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    UNIQUE (pmid, model, prompt_version, screened_at)
);

CREATE INDEX IF NOT EXISTS llm_screens_latest
ON llm_screens(pmid, imported_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS audit_samples (
    sample_id TEXT NOT NULL,
    pmid TEXT NOT NULL REFERENCES articles(pmid) ON DELETE CASCADE,
    source_relevance TEXT NOT NULL CHECK (source_relevance IN ('NO')),
    fraction REAL NOT NULL CHECK (fraction > 0 AND fraction <= 1),
    seed TEXT NOT NULL,
    hash_rank TEXT NOT NULL,
    sampled_at TEXT NOT NULL,
    PRIMARY KEY (sample_id, pmid)
);

CREATE TABLE IF NOT EXISTS human_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pmid TEXT NOT NULL REFERENCES articles(pmid) ON DELETE CASCADE,
    decision TEXT NOT NULL CHECK (decision IN ('INCLUDE', 'EXCLUDE', 'UNCLEAR')),
    computational_story_central INTEGER CHECK (computational_story_central IN (0, 1)),
    reason TEXT NOT NULL,
    reviewer TEXT NOT NULL,
    reviewed_at TEXT NOT NULL
);
"""


def require_outside_repo(path: str | Path) -> Path:
    resolved = Path(path).expanduser().resolve()
    if resolved == REPO_ROOT or resolved.is_relative_to(REPO_ROOT):
        raise ValueError(
            f"Data payload path must be outside the repository: {resolved}. "
            "Set ARTICLE_BLUEPRINT_DATA to the workspace DATA tree."
        )
    return resolved


def connect(path: str | Path) -> sqlite3.Connection:
    db_path = require_outside_repo(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def init_db(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA_SQL)
    connection.execute(
        "INSERT INTO schema_meta(key, value) VALUES('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(SCHEMA_VERSION),),
    )
    connection.commit()


@contextmanager
def transaction(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    try:
        connection.execute("BEGIN")
        yield connection
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
