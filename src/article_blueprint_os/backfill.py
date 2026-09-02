from __future__ import annotations

import json
import sqlite3
import subprocess
import uuid
from datetime import date
from pathlib import Path
from typing import Callable

from .config import Journal, JournalRegistry
from .db import REPO_ROOT, require_outside_repo
from .pipeline import build_query, enumerate_journal
from .pubmed import PubMedClient, utc_now


ProgressCallback = Callable[[str], None]


def detect_software_revision() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    revision = result.stdout.strip()
    return revision or "unknown"


def _years_in_window(start_date: str, end_date: str) -> range:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    if start > end:
        raise ValueError("start date must not be after end date")
    return range(start.year, end.year + 1)


def create_backfill(
    connection: sqlite3.Connection,
    registry: JournalRegistry,
    *,
    start_date: str,
    end_date: str,
    software_revision: str,
) -> str:
    _years_in_window(start_date, end_date)
    backfill_id = str(uuid.uuid4())
    started_at = utc_now()
    with connection:
        connection.execute(
            """
            INSERT INTO historical_backfills(
                backfill_id, registry_version, start_date, end_date,
                software_revision, journal_count, status, started_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'running', ?)
            """,
            (
                backfill_id,
                registry.version,
                start_date,
                end_date,
                software_revision,
                len(registry.journals),
                started_at,
            ),
        )
        connection.executemany(
            """
            INSERT INTO historical_backfill_journals(
                backfill_id, journal_key, status
            ) VALUES (?, ?, 'pending')
            """,
            ((backfill_id, journal.key) for journal in registry.journals),
        )
    return backfill_id


def validate_resume(
    connection: sqlite3.Connection,
    registry: JournalRegistry,
    backfill_id: str,
    *,
    start_date: str,
    end_date: str,
) -> None:
    row = connection.execute(
        "SELECT * FROM historical_backfills WHERE backfill_id=?", (backfill_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown backfill id: {backfill_id}")
    expected = (registry.version, start_date, end_date, len(registry.journals))
    actual = (
        row["registry_version"],
        row["start_date"],
        row["end_date"],
        row["journal_count"],
    )
    if actual != expected:
        raise ValueError(
            "Resume parameters do not match the stored backfill: "
            f"stored={actual!r}, requested={expected!r}"
        )
    stored_keys = {
        item["journal_key"]
        for item in connection.execute(
            "SELECT journal_key FROM historical_backfill_journals WHERE backfill_id=?",
            (backfill_id,),
        )
    }
    registry_keys = {journal.key for journal in registry.journals}
    if stored_keys != registry_keys:
        raise ValueError("Stored backfill journal set does not match the registry")
    with connection:
        connection.execute(
            "UPDATE historical_backfills SET status='running', completed_at=NULL WHERE backfill_id=?",
            (backfill_id,),
        )


def _annual_bounds(year: int, start_date: str, end_date: str) -> tuple[str, str]:
    return max(start_date, f"{year}-01-01"), min(end_date, f"{year}-12-31")


def reconcile_annual_coverage(
    connection: sqlite3.Connection,
    client: PubMedClient,
    journal: Journal,
    *,
    backfill_id: str,
    enumeration_run_id: str,
    start_date: str,
    end_date: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for year in _years_in_window(start_date, end_date):
        annual_start, annual_end = _annual_bounds(year, start_date, end_date)
        query = build_query(journal, annual_start, annual_end)
        expected_count = client.search_history(query).count
        observed_count = connection.execute(
            """
            SELECT COUNT(DISTINCT membership.pmid)
            FROM enumeration_membership AS membership
            JOIN articles ON articles.pmid = membership.pmid
            WHERE membership.run_id=? AND articles.publication_year=?
            """,
            (enumeration_run_id, year),
        ).fetchone()[0]
        status = "match" if expected_count == observed_count else "discrepancy"
        checked_at = utc_now()
        with connection:
            connection.execute(
                """
                INSERT INTO annual_coverage_checks(
                    backfill_id, journal_key, enumeration_run_id, year, query,
                    expected_count, observed_count, status, checked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(backfill_id, journal_key, year) DO UPDATE SET
                    enumeration_run_id=excluded.enumeration_run_id,
                    query=excluded.query,
                    expected_count=excluded.expected_count,
                    observed_count=excluded.observed_count,
                    status=excluded.status,
                    checked_at=excluded.checked_at
                """,
                (
                    backfill_id,
                    journal.key,
                    enumeration_run_id,
                    year,
                    query,
                    expected_count,
                    observed_count,
                    status,
                    checked_at,
                ),
            )
        rows.append(
            {
                "journal_key": journal.key,
                "year": year,
                "expected_count": expected_count,
                "observed_count": observed_count,
                "status": status,
            }
        )
    return rows


def run_historical_backfill(
    connection: sqlite3.Connection,
    client: PubMedClient,
    registry: JournalRegistry,
    *,
    start_date: str,
    end_date: str,
    raw_dir: str | Path,
    batch_size: int = 200,
    software_revision: str | None = None,
    resume_id: str | None = None,
    progress: ProgressCallback | None = None,
) -> dict[str, object]:
    raw_root = require_outside_repo(raw_dir)
    if resume_id is None:
        backfill_id = create_backfill(
            connection,
            registry,
            start_date=start_date,
            end_date=end_date,
            software_revision=software_revision or detect_software_revision(),
        )
    else:
        backfill_id = resume_id
        validate_resume(
            connection,
            registry,
            backfill_id,
            start_date=start_date,
            end_date=end_date,
        )

    for journal in registry.journals:
        state = connection.execute(
            """
            SELECT status FROM historical_backfill_journals
            WHERE backfill_id=? AND journal_key=?
            """,
            (backfill_id, journal.key),
        ).fetchone()[0]
        if state == "complete":
            if progress:
                progress(f"{journal.key}: already complete; skipped")
            continue
        started_at = utc_now()
        with connection:
            connection.execute(
                """
                UPDATE historical_backfill_journals
                SET status='running', attempt_count=attempt_count+1,
                    error=NULL, started_at=?, completed_at=NULL
                WHERE backfill_id=? AND journal_key=?
                """,
                (started_at, backfill_id, journal.key),
            )
        try:
            result = enumerate_journal(
                connection,
                client,
                registry,
                journal,
                start_date=start_date,
                end_date=end_date,
                batch_size=batch_size,
                raw_dir=raw_root,
                progress=progress,
            )
            reconcile_annual_coverage(
                connection,
                client,
                journal,
                backfill_id=backfill_id,
                enumeration_run_id=str(result["run_id"]),
                start_date=start_date,
                end_date=end_date,
            )
            with connection:
                connection.execute(
                    """
                    UPDATE historical_backfill_journals
                    SET enumeration_run_id=?, status='complete', completed_at=?
                    WHERE backfill_id=? AND journal_key=?
                    """,
                    (result["run_id"], utc_now(), backfill_id, journal.key),
                )
        except Exception as exc:
            with connection:
                connection.execute(
                    """
                    UPDATE historical_backfill_journals
                    SET status='failed', error=?, completed_at=?
                    WHERE backfill_id=? AND journal_key=?
                    """,
                    (str(exc), utc_now(), backfill_id, journal.key),
                )
            if progress:
                progress(f"{journal.key}: failed: {exc}")

    summary = backfill_summary(connection, backfill_id)
    final_status = "failed" if summary["failed_journals"] else "complete"
    with connection:
        connection.execute(
            """
            UPDATE historical_backfills
            SET status=?, completed_at=? WHERE backfill_id=?
            """,
            (final_status, utc_now(), backfill_id),
        )
    summary = backfill_summary(connection, backfill_id)
    if final_status == "failed":
        raise RuntimeError(
            f"Backfill {backfill_id} is incomplete: "
            f"{summary['failed_journals']} journal(s) failed"
        )
    return summary


def backfill_summary(connection: sqlite3.Connection, backfill_id: str) -> dict[str, object]:
    run = connection.execute(
        "SELECT * FROM historical_backfills WHERE backfill_id=?", (backfill_id,)
    ).fetchone()
    if run is None:
        raise ValueError(f"Unknown backfill id: {backfill_id}")
    states = {
        row["status"]: row["count"]
        for row in connection.execute(
            """
            SELECT status, COUNT(*) AS count
            FROM historical_backfill_journals
            WHERE backfill_id=? GROUP BY status
            """,
            (backfill_id,),
        )
    }
    coverage = connection.execute(
        """
        SELECT COUNT(*) AS checked,
               SUM(CASE WHEN status='discrepancy' THEN 1 ELSE 0 END) AS discrepancies
        FROM annual_coverage_checks WHERE backfill_id=?
        """,
        (backfill_id,),
    ).fetchone()
    article_count = connection.execute(
        """
        SELECT COUNT(DISTINCT membership.pmid)
        FROM historical_backfill_journals AS journals
        JOIN enumeration_membership AS membership
          ON membership.run_id = journals.enumeration_run_id
        WHERE journals.backfill_id=? AND journals.status='complete'
        """,
        (backfill_id,),
    ).fetchone()[0]
    return {
        "backfill_id": backfill_id,
        "registry_version": run["registry_version"],
        "start_date": run["start_date"],
        "end_date": run["end_date"],
        "software_revision": run["software_revision"],
        "status": run["status"],
        "journal_count": run["journal_count"],
        "completed_journals": states.get("complete", 0),
        "failed_journals": states.get("failed", 0),
        "pending_journals": states.get("pending", 0) + states.get("running", 0),
        "unique_articles": article_count,
        "annual_checks": coverage["checked"] or 0,
        "annual_discrepancies": coverage["discrepancies"] or 0,
        "started_at": run["started_at"],
        "completed_at": run["completed_at"],
    }


def export_coverage_report(
    connection: sqlite3.Connection, backfill_id: str, output_path: str | Path
) -> dict[str, object]:
    destination = require_outside_repo(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = backfill_summary(connection, backfill_id)
    payload["journals"] = [
        dict(row)
        for row in connection.execute(
            """
            SELECT journal_key, enumeration_run_id, status, attempt_count, error,
                   started_at, completed_at
            FROM historical_backfill_journals
            WHERE backfill_id=? ORDER BY journal_key
            """,
            (backfill_id,),
        )
    ]
    payload["annual_coverage"] = [
        dict(row)
        for row in connection.execute(
            """
            SELECT journal_key, year, expected_count, observed_count, status,
                   query, enumeration_run_id, checked_at
            FROM annual_coverage_checks
            WHERE backfill_id=? ORDER BY journal_key, year
            """,
            (backfill_id,),
        )
    ]
    partial = destination.with_suffix(destination.suffix + ".partial")
    partial.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    partial.replace(destination)
    return payload
