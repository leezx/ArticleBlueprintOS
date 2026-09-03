from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


SCHEMA_VERSION = 6
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

CREATE TABLE IF NOT EXISTS historical_backfills (
    backfill_id TEXT PRIMARY KEY,
    registry_version TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    software_revision TEXT NOT NULL,
    journal_count INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'complete', 'failed')),
    started_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS historical_backfill_journals (
    backfill_id TEXT NOT NULL REFERENCES historical_backfills(backfill_id) ON DELETE CASCADE,
    journal_key TEXT NOT NULL,
    enumeration_run_id TEXT REFERENCES enumeration_runs(run_id),
    status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'complete', 'failed')),
    attempt_count INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    started_at TEXT,
    completed_at TEXT,
    PRIMARY KEY (backfill_id, journal_key)
);

CREATE TABLE IF NOT EXISTS annual_coverage_checks (
    backfill_id TEXT NOT NULL REFERENCES historical_backfills(backfill_id) ON DELETE CASCADE,
    journal_key TEXT NOT NULL,
    enumeration_run_id TEXT NOT NULL REFERENCES enumeration_runs(run_id),
    year INTEGER NOT NULL,
    query TEXT NOT NULL,
    expected_count INTEGER NOT NULL,
    observed_count INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('match', 'discrepancy')),
    checked_at TEXT NOT NULL,
    PRIMARY KEY (backfill_id, journal_key, year)
);

CREATE TABLE IF NOT EXISTS historical_backfill_slices (
    backfill_id TEXT NOT NULL REFERENCES historical_backfills(backfill_id) ON DELETE CASCADE,
    journal_key TEXT NOT NULL,
    slice_start TEXT NOT NULL,
    slice_end TEXT NOT NULL,
    planned_count INTEGER NOT NULL,
    enumeration_run_id TEXT REFERENCES enumeration_runs(run_id),
    status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'complete', 'failed')),
    attempt_count INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    started_at TEXT,
    completed_at TEXT,
    PRIMARY KEY (backfill_id, journal_key, slice_start, slice_end)
);

CREATE TABLE IF NOT EXISTS backfill_coverage_checks (
    backfill_id TEXT NOT NULL REFERENCES historical_backfills(backfill_id) ON DELETE CASCADE,
    journal_key TEXT NOT NULL,
    scope TEXT NOT NULL CHECK (scope IN ('full_window', 'annual')),
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    query TEXT NOT NULL,
    expected_count INTEGER NOT NULL,
    observed_count INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('match', 'discrepancy')),
    checked_at TEXT NOT NULL,
    PRIMARY KEY (backfill_id, journal_key, scope, period_start, period_end)
);

CREATE TABLE IF NOT EXISTS calibration_samples (
    calibration_id TEXT PRIMARY KEY,
    seed TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS calibration_sample_items (
    calibration_id TEXT NOT NULL REFERENCES calibration_samples(calibration_id) ON DELETE CASCADE,
    pmid TEXT NOT NULL REFERENCES articles(pmid) ON DELETE CASCADE,
    stratum TEXT NOT NULL CHECK (stratum IN ('candidate_priority', 'non_priority_original_or_unclear', 'obvious_non_original')),
    population_size INTEGER NOT NULL,
    hash_rank TEXT NOT NULL,
    selected_at TEXT NOT NULL,
    PRIMARY KEY (calibration_id, pmid)
);

CREATE TABLE IF NOT EXISTS llm_batch_attempts (
    batch_id TEXT NOT NULL,
    attempt INTEGER NOT NULL,
    input_path TEXT NOT NULL,
    input_sha256 TEXT NOT NULL,
    output_path TEXT,
    output_sha256 TEXT,
    model TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'complete', 'failed')),
    error TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    PRIMARY KEY (batch_id, attempt)
);

CREATE TABLE IF NOT EXISTS manual_web_attempts (
    batch_id TEXT NOT NULL, attempt INTEGER NOT NULL,
    calibration_id TEXT NOT NULL REFERENCES calibration_samples(calibration_id),
    provider_route TEXT NOT NULL CHECK (provider_route = 'ChatGPT Web UI'),
    execution_mode TEXT NOT NULL CHECK (execution_mode IN ('manual', 'automated_browser')),
    model_display_name TEXT, model_identifier_precision TEXT NOT NULL,
    operator TEXT, prompt_version TEXT NOT NULL, software_revision TEXT NOT NULL,
    input_path TEXT NOT NULL, input_sha256 TEXT NOT NULL,
    output_path TEXT, output_sha256 TEXT, record_count INTEGER NOT NULL,
    wrapper_version TEXT, wrapper_sha256 TEXT,
    fresh_chat_confirmed INTEGER NOT NULL CHECK (fresh_chat_confirmed IN (0,1)),
    temperature TEXT NOT NULL, maximum_output_tokens TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('prepared','valid','failed')),
    error TEXT, created_at TEXT NOT NULL, submitted_at TEXT, executed_at TEXT,
    completed_at TEXT,
    PRIMARY KEY (batch_id, attempt)
);

CREATE TABLE IF NOT EXISTS manual_web_attempt_items (
    batch_id TEXT NOT NULL,
    attempt INTEGER NOT NULL,
    pmid TEXT NOT NULL REFERENCES articles(pmid),
    ordinal INTEGER NOT NULL,
    llm_screen_id INTEGER REFERENCES llm_screens(id),
    PRIMARY KEY (batch_id, attempt, pmid),
    UNIQUE (batch_id, attempt, ordinal),
    FOREIGN KEY (batch_id, attempt)
        REFERENCES manual_web_attempts(batch_id, attempt) ON DELETE CASCADE
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
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='manual_web_attempts'"
    ).fetchone()
    if row and "execution_mode = 'manual'" in row[0]:
        # Ensure the pragma is applied outside any transaction; otherwise SQLite
        # silently ignores the toggle and can leave the rebuild half-constrained.
        connection.commit()
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("BEGIN")
        try:
            connection.execute("ALTER TABLE manual_web_attempt_items RENAME TO manual_web_attempt_items_legacy")
            connection.execute("ALTER TABLE manual_web_attempts RENAME TO manual_web_attempts_legacy")
            connection.execute("""CREATE TABLE manual_web_attempts (
                batch_id TEXT NOT NULL, attempt INTEGER NOT NULL,
                calibration_id TEXT NOT NULL REFERENCES calibration_samples(calibration_id),
                provider_route TEXT NOT NULL CHECK (provider_route = 'ChatGPT Web UI'),
                execution_mode TEXT NOT NULL CHECK (execution_mode IN ('manual', 'automated_browser')),
                model_display_name TEXT, model_identifier_precision TEXT NOT NULL,
                operator TEXT, prompt_version TEXT NOT NULL, software_revision TEXT NOT NULL,
                input_path TEXT NOT NULL, input_sha256 TEXT NOT NULL, output_path TEXT,
                output_sha256 TEXT, record_count INTEGER NOT NULL,
                wrapper_version TEXT, wrapper_sha256 TEXT,
                fresh_chat_confirmed INTEGER NOT NULL CHECK (fresh_chat_confirmed IN (0,1)),
                temperature TEXT NOT NULL, maximum_output_tokens TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('prepared','valid','failed')),
                error TEXT, created_at TEXT NOT NULL, submitted_at TEXT, executed_at TEXT,
                completed_at TEXT, PRIMARY KEY (batch_id, attempt))""")
            connection.execute("""INSERT INTO manual_web_attempts
                SELECT batch_id,attempt,calibration_id,provider_route,execution_mode,
                model_display_name,model_identifier_precision,operator,prompt_version,
                software_revision,input_path,input_sha256,output_path,output_sha256,
                record_count,NULL,NULL,fresh_chat_confirmed,temperature,
                maximum_output_tokens,status,error,created_at,submitted_at,executed_at,completed_at
                FROM manual_web_attempts_legacy""")
            connection.execute("""CREATE TABLE manual_web_attempt_items (
                batch_id TEXT NOT NULL, attempt INTEGER NOT NULL,
                pmid TEXT NOT NULL REFERENCES articles(pmid), ordinal INTEGER NOT NULL,
                llm_screen_id INTEGER REFERENCES llm_screens(id),
                PRIMARY KEY (batch_id, attempt, pmid), UNIQUE (batch_id, attempt, ordinal),
                FOREIGN KEY (batch_id, attempt) REFERENCES manual_web_attempts(batch_id, attempt) ON DELETE CASCADE)""")
            connection.execute("INSERT INTO manual_web_attempt_items SELECT * FROM manual_web_attempt_items_legacy")
            connection.execute("DROP TABLE manual_web_attempt_items_legacy")
            connection.execute("DROP TABLE manual_web_attempts_legacy")
            violations = connection.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise RuntimeError(f"foreign-key check failed during schema migration: {violations}")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.execute("PRAGMA foreign_keys=ON")
    connection.commit()
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
