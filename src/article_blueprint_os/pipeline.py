from __future__ import annotations

import sqlite3
import uuid
from datetime import date
from pathlib import Path
from typing import Callable

from .config import Journal, JournalRegistry
from .db import json_text, require_outside_repo
from .pubmed import Article, PubMedClient, utc_now


ProgressCallback = Callable[[str], None]


def build_query(journal: Journal, start_date: str, end_date: str) -> str:
    _validate_date(start_date)
    _validate_date(end_date)
    if start_date > end_date:
        raise ValueError("start date must not be after end date")
    return (
        f"{journal.pubmed_term} AND "
        f'("{start_date}"[Date - Publication] : "{end_date}"[Date - Publication])'
    )


def _validate_date(value: str) -> None:
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Expected an ISO date (YYYY-MM-DD), got {value!r}") from exc


def _upsert_article(
    connection: sqlite3.Connection,
    *,
    run_id: str,
    journal_key: str,
    article: Article,
    ordinal: int,
    observed_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO articles(
            pmid, doi, journal_key, source_journal_title, publication_date,
            publication_date_precision, publication_year, title, abstract,
            article_types_json, authors_json, mesh_terms_json, pubmed_url,
            first_seen_run_id, last_seen_run_id, source_updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(pmid) DO UPDATE SET
            doi=excluded.doi,
            journal_key=excluded.journal_key,
            source_journal_title=excluded.source_journal_title,
            publication_date=excluded.publication_date,
            publication_date_precision=excluded.publication_date_precision,
            publication_year=excluded.publication_year,
            title=excluded.title,
            abstract=excluded.abstract,
            article_types_json=excluded.article_types_json,
            authors_json=excluded.authors_json,
            mesh_terms_json=excluded.mesh_terms_json,
            pubmed_url=excluded.pubmed_url,
            last_seen_run_id=excluded.last_seen_run_id,
            source_updated_at=excluded.source_updated_at
        """,
        (
            article.pmid,
            article.doi,
            journal_key,
            article.source_journal_title,
            article.publication_date,
            article.publication_date_precision,
            article.publication_year,
            article.title,
            article.abstract,
            json_text(article.article_types),
            json_text(article.authors),
            json_text(article.mesh_terms),
            f"https://pubmed.ncbi.nlm.nih.gov/{article.pmid}/",
            run_id,
            run_id,
            observed_at,
        ),
    )
    connection.execute(
        "INSERT OR IGNORE INTO enumeration_membership(run_id, pmid, ordinal) VALUES (?, ?, ?)",
        (run_id, article.pmid, ordinal),
    )


def enumerate_journal(
    connection: sqlite3.Connection,
    client: PubMedClient,
    registry: JournalRegistry,
    journal: Journal,
    *,
    start_date: str,
    end_date: str,
    batch_size: int = 200,
    raw_dir: str | Path | None = None,
    progress: ProgressCallback | None = None,
) -> dict[str, object]:
    query = build_query(journal, start_date, end_date)
    run_id = str(uuid.uuid4())
    started_at = utc_now()
    connection.execute(
        """
        INSERT INTO enumeration_runs(
            run_id, journal_key, journal_title, registry_version, query,
            start_date, end_date, status, started_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'running', ?)
        """,
        (
            run_id,
            journal.key,
            journal.title,
            registry.version,
            query,
            start_date,
            end_date,
            started_at,
        ),
    )
    connection.commit()
    try:
        raw_run_dir = None
        if raw_dir is not None:
            raw_run_dir = require_outside_repo(raw_dir) / run_id
            raw_run_dir.mkdir(parents=True, exist_ok=False)
        history = client.search_history(query)
        connection.execute(
            "UPDATE enumeration_runs SET expected_count=? WHERE run_id=?",
            (history.count, run_id),
        )
        connection.commit()
        unique_pmids: set[str] = set()
        fetched_count = 0
        for batch in client.fetch_history(history, batch_size=batch_size):
            start = batch.retstart
            articles = batch.articles
            raw_path = None
            if raw_run_dir is not None:
                raw_path = raw_run_dir / f"batch_{start:08d}.xml"
                partial_path = raw_path.with_suffix(".xml.partial")
                partial_path.write_bytes(batch.raw_xml)
                partial_path.replace(raw_path)
            observed_at = utc_now()
            with connection:
                for offset, article in enumerate(articles):
                    ordinal = start + offset
                    _upsert_article(
                        connection,
                        run_id=run_id,
                        journal_key=journal.key,
                        article=article,
                        ordinal=ordinal,
                        observed_at=observed_at,
                    )
                    unique_pmids.add(article.pmid)
                fetched_count += len(articles)
                connection.execute(
                    "UPDATE enumeration_runs SET fetched_count=?, unique_count=? WHERE run_id=?",
                    (fetched_count, len(unique_pmids), run_id),
                )
                if raw_path is not None:
                    connection.execute(
                        """
                        INSERT INTO enumeration_batches(
                            run_id, retstart, record_count, raw_xml_path,
                            byte_size, sha256
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            run_id,
                            start,
                            len(articles),
                            str(raw_path),
                            len(batch.raw_xml),
                            batch.sha256,
                        ),
                    )
            if progress:
                progress(f"{journal.key}: {fetched_count}/{history.count}")
        if fetched_count != history.count or len(unique_pmids) != history.count:
            raise RuntimeError(
                f"Coverage mismatch for {journal.key}: PubMed reported {history.count}, "
                f"parsed {fetched_count}, unique PMIDs {len(unique_pmids)}"
            )
        completed_at = utc_now()
        connection.execute(
            """
            UPDATE enumeration_runs
            SET status='complete', fetched_count=?, unique_count=?, completed_at=?
            WHERE run_id=?
            """,
            (fetched_count, len(unique_pmids), completed_at, run_id),
        )
        connection.commit()
        return {
            "run_id": run_id,
            "journal_key": journal.key,
            "expected_count": history.count,
            "fetched_count": fetched_count,
            "unique_count": len(unique_pmids),
            "status": "complete",
        }
    except Exception as exc:
        connection.execute(
            "UPDATE enumeration_runs SET status='failed', error=?, completed_at=? WHERE run_id=?",
            (str(exc), utc_now(), run_id),
        )
        connection.commit()
        raise
