from __future__ import annotations

import json
import sqlite3
import subprocess
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

from .config import Journal, JournalRegistry
from .db import REPO_ROOT, require_outside_repo
from .pipeline import build_query, enumerate_journal
from .pubmed import PubMedClient, utc_now


ProgressCallback = Callable[[str], None]
PUBMED_MAX_ACCESSIBLE_RESULTS = 9_999


@dataclass(frozen=True)
class DateSlice:
    start_date: str
    end_date: str
    expected_count: int


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


def plan_date_slices(
    client: PubMedClient,
    journal: Journal,
    *,
    start_date: str,
    end_date: str,
    max_results: int = PUBMED_MAX_ACCESSIBLE_RESULTS,
) -> list[DateSlice]:
    """Recursively partition a PubMed query below its accessible result limit."""
    if max_results < 1:
        raise ValueError("max_results must be positive")
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    if start > end:
        raise ValueError("start date must not be after end date")

    def split(left: date, right: date) -> list[DateSlice]:
        left_text, right_text = left.isoformat(), right.isoformat()
        count = client.search_history(build_query(journal, left_text, right_text)).count
        if count <= max_results:
            return [DateSlice(left_text, right_text, count)]
        if left == right:
            raise RuntimeError(
                f"PubMed query for {journal.key} has {count} results on {left_text}; "
                f"cannot partition below the {max_results}-record limit"
            )
        midpoint = left + timedelta(days=(right - left).days // 2)
        return split(left, midpoint) + split(midpoint + timedelta(days=1), right)

    return split(start, end)


def _store_coverage_check(
    connection: sqlite3.Connection,
    journal: Journal,
    *,
    backfill_id: str,
    scope: str,
    start_date: str,
    end_date: str,
    expected_count: int,
    observed_count: int,
) -> str:
    status = "match" if expected_count == observed_count else "discrepancy"
    with connection:
        connection.execute(
            """
            INSERT INTO backfill_coverage_checks(
                backfill_id, journal_key, scope, period_start, period_end,
                query, expected_count, observed_count, status, checked_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(backfill_id, journal_key, scope, period_start, period_end)
            DO UPDATE SET
                query=excluded.query,
                expected_count=excluded.expected_count,
                observed_count=excluded.observed_count,
                status=excluded.status,
                checked_at=excluded.checked_at
            """,
            (
                backfill_id,
                journal.key,
                scope,
                start_date,
                end_date,
                build_query(journal, start_date, end_date),
                expected_count,
                observed_count,
                status,
                utc_now(),
            ),
        )
    return status


def _slice_union_count(
    connection: sqlite3.Connection,
    backfill_id: str,
    journal_key: str,
    *,
    publication_year: int | None = None,
) -> int:
    year_clause = "" if publication_year is None else "AND articles.publication_year=?"
    parameters: tuple[object, ...] = (backfill_id, journal_key)
    if publication_year is not None:
        parameters += (publication_year,)
    return connection.execute(
        f"""
        SELECT COUNT(DISTINCT membership.pmid)
        FROM historical_backfill_slices AS slices
        JOIN enumeration_membership AS membership
          ON membership.run_id = slices.enumeration_run_id
        JOIN articles ON articles.pmid = membership.pmid
        WHERE slices.backfill_id=? AND slices.journal_key=?
          AND slices.status='complete' {year_clause}
        """,
        parameters,
    ).fetchone()[0]


def reconcile_partitioned_coverage(
    connection: sqlite3.Connection,
    client: PubMedClient,
    journal: Journal,
    *,
    backfill_id: str,
    start_date: str,
    end_date: str,
    full_expected_count: int,
) -> str:
    full_observed_count = _slice_union_count(connection, backfill_id, journal.key)
    full_status = _store_coverage_check(
        connection,
        journal,
        backfill_id=backfill_id,
        scope="full_window",
        start_date=start_date,
        end_date=end_date,
        expected_count=full_expected_count,
        observed_count=full_observed_count,
    )
    for year in _years_in_window(start_date, end_date):
        annual_start, annual_end = _annual_bounds(year, start_date, end_date)
        expected_count = client.search_history(
            build_query(journal, annual_start, annual_end)
        ).count
        observed_count = _slice_union_count(
            connection, backfill_id, journal.key, publication_year=year
        )
        _store_coverage_check(
            connection,
            journal,
            backfill_id=backfill_id,
            scope="annual",
            start_date=annual_start,
            end_date=annual_end,
            expected_count=expected_count,
            observed_count=observed_count,
        )
    return full_status


def run_historical_backfill(
    connection: sqlite3.Connection,
    client: PubMedClient,
    registry: JournalRegistry,
    *,
    start_date: str,
    end_date: str,
    raw_dir: str | Path,
    batch_size: int = 200,
    max_slice_results: int = PUBMED_MAX_ACCESSIBLE_RESULTS,
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
            full_expected_count = client.search_history(
                build_query(journal, start_date, end_date)
            ).count
            planned_slices = plan_date_slices(
                client,
                journal,
                start_date=start_date,
                end_date=end_date,
                max_results=max_slice_results,
            )
            with connection:
                connection.executemany(
                    """
                    INSERT OR IGNORE INTO historical_backfill_slices(
                        backfill_id, journal_key, slice_start, slice_end,
                        planned_count, status
                    ) VALUES (?, ?, ?, ?, ?, 'pending')
                    """,
                    (
                        (
                            backfill_id,
                            journal.key,
                            item.start_date,
                            item.end_date,
                            item.expected_count,
                        )
                        for item in planned_slices
                    ),
                )
            stored_slices = {
                (row["slice_start"], row["slice_end"])
                for row in connection.execute(
                    """
                    SELECT slice_start, slice_end, planned_count
                    FROM historical_backfill_slices
                    WHERE backfill_id=? AND journal_key=?
                    """,
                    (backfill_id, journal.key),
                )
            }
            expected_slices = {(item.start_date, item.end_date) for item in planned_slices}
            if stored_slices != expected_slices:
                raise RuntimeError(
                    f"Stored date partition for {journal.key} differs from the current plan"
                )
            if progress:
                progress(
                    f"{journal.key}: planned {len(planned_slices)} slice(s), "
                    f"{full_expected_count} full-window records; slice counts may overlap"
                )
            for item in planned_slices:
                slice_row = connection.execute(
                    """
                    SELECT status FROM historical_backfill_slices
                    WHERE backfill_id=? AND journal_key=?
                      AND slice_start=? AND slice_end=?
                    """,
                    (backfill_id, journal.key, item.start_date, item.end_date),
                ).fetchone()
                if slice_row["status"] == "complete":
                    if progress:
                        progress(
                            f"{journal.key} {item.start_date}..{item.end_date}: "
                            "already complete; skipped"
                        )
                    continue
                with connection:
                    connection.execute(
                        """
                        UPDATE historical_backfill_slices
                        SET status='running', attempt_count=attempt_count+1,
                            error=NULL, started_at=?, completed_at=NULL
                        WHERE backfill_id=? AND journal_key=?
                          AND slice_start=? AND slice_end=?
                        """,
                        (
                            utc_now(),
                            backfill_id,
                            journal.key,
                            item.start_date,
                            item.end_date,
                        ),
                    )
                try:
                    result = enumerate_journal(
                        connection,
                        client,
                        registry,
                        journal,
                        start_date=item.start_date,
                        end_date=item.end_date,
                        batch_size=batch_size,
                        raw_dir=raw_root,
                        progress=progress,
                    )
                except Exception as exc:
                    with connection:
                        connection.execute(
                            """
                            UPDATE historical_backfill_slices
                            SET status='failed', error=?, completed_at=?
                            WHERE backfill_id=? AND journal_key=?
                              AND slice_start=? AND slice_end=?
                            """,
                            (
                                str(exc),
                                utc_now(),
                                backfill_id,
                                journal.key,
                                item.start_date,
                                item.end_date,
                            ),
                        )
                    raise
                with connection:
                    connection.execute(
                        """
                        UPDATE historical_backfill_slices
                        SET enumeration_run_id=?, status='complete', completed_at=?
                        WHERE backfill_id=? AND journal_key=?
                          AND slice_start=? AND slice_end=?
                        """,
                        (
                            result["run_id"],
                            utc_now(),
                            backfill_id,
                            journal.key,
                            item.start_date,
                            item.end_date,
                        ),
                    )
            full_status = reconcile_partitioned_coverage(
                connection,
                client,
                journal,
                backfill_id=backfill_id,
                start_date=start_date,
                end_date=end_date,
                full_expected_count=full_expected_count,
            )
            if full_status != "match":
                observed = _slice_union_count(connection, backfill_id, journal.key)
                raise RuntimeError(
                    f"Partitioned coverage mismatch for {journal.key}: "
                    f"full query reported {full_expected_count}, slice union has {observed}"
                )
            with connection:
                connection.execute(
                    """
                    UPDATE historical_backfill_journals
                    SET enumeration_run_id=NULL, status='complete', completed_at=?
                    WHERE backfill_id=? AND journal_key=?
                    """,
                    (utc_now(), backfill_id, journal.key),
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
        FROM backfill_coverage_checks
        WHERE backfill_id=? AND scope='annual'
        """,
        (backfill_id,),
    ).fetchone()
    full_coverage = connection.execute(
        """
        SELECT COUNT(*) AS checked,
               SUM(CASE WHEN status='discrepancy' THEN 1 ELSE 0 END) AS discrepancies
        FROM backfill_coverage_checks
        WHERE backfill_id=? AND scope='full_window'
        """,
        (backfill_id,),
    ).fetchone()
    article_count = connection.execute(
        """
        SELECT COUNT(DISTINCT membership.pmid)
        FROM historical_backfill_slices AS slices
        JOIN enumeration_membership AS membership
          ON membership.run_id = slices.enumeration_run_id
        WHERE slices.backfill_id=? AND slices.status='complete'
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
        "full_window_checks": full_coverage["checked"] or 0,
        "full_window_discrepancies": full_coverage["discrepancies"] or 0,
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
            SELECT journal_key, period_start, period_end, expected_count,
                   observed_count, status, query, checked_at
            FROM backfill_coverage_checks
            WHERE backfill_id=? AND scope='annual'
            ORDER BY journal_key, period_start
            """,
            (backfill_id,),
        )
    ]
    payload["full_window_coverage"] = [
        dict(row)
        for row in connection.execute(
            """
            SELECT journal_key, period_start, period_end, expected_count,
                   observed_count, status, query, checked_at
            FROM backfill_coverage_checks
            WHERE backfill_id=? AND scope='full_window'
            ORDER BY journal_key
            """,
            (backfill_id,),
        )
    ]
    payload["slices"] = [
        dict(row)
        for row in connection.execute(
            """
            SELECT journal_key, slice_start, slice_end, planned_count,
                   enumeration_run_id, status, attempt_count, error,
                   started_at, completed_at
            FROM historical_backfill_slices
            WHERE backfill_id=? ORDER BY journal_key, slice_start
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
