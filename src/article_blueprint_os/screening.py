from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass

from .config import ScreeningRules
from .db import json_text
from .pubmed import utc_now


NON_ORIGINAL_TYPES = frozenset(
    {
        "review",
        "systematic review",
        "meta-analysis",
        "editorial",
        "comment",
        "news",
        "letter",
        "published erratum",
        "retracted publication",
    }
)


@dataclass(frozen=True)
class ScreenResult:
    cancer_terms: tuple[str, ...]
    omics_terms: tuple[str, ...]
    candidate_priority: bool
    obvious_non_original_type: bool


def _matches(patterns: tuple[str, ...], text: str) -> tuple[str, ...]:
    return tuple(pattern for pattern in patterns if re.search(pattern, text, flags=re.I))


def screen_text(
    rules: ScreeningRules,
    *,
    title: str,
    abstract: str,
    mesh_terms: list[str] | tuple[str, ...],
    article_types: list[str] | tuple[str, ...],
) -> ScreenResult:
    text = "\n".join((title, abstract, "\n".join(mesh_terms)))
    cancer_terms = _matches(rules.cancer, text)
    omics_terms = _matches(rules.omics, text)
    normalized_types = {value.casefold() for value in article_types}
    obvious_non_original = bool(normalized_types & NON_ORIGINAL_TYPES)
    return ScreenResult(
        cancer_terms=cancer_terms,
        omics_terms=omics_terms,
        candidate_priority=bool(cancer_terms and omics_terms and not obvious_non_original),
        obvious_non_original_type=obvious_non_original,
    )


def screen_database(connection: sqlite3.Connection, rules: ScreeningRules) -> dict[str, int]:
    rows = connection.execute(
        "SELECT pmid, title, abstract, mesh_terms_json, article_types_json FROM articles"
    ).fetchall()
    candidate_count = 0
    non_original_count = 0
    screened_at = utc_now()
    with connection:
        for row in rows:
            result = screen_text(
                rules,
                title=row["title"],
                abstract=row["abstract"],
                mesh_terms=json.loads(row["mesh_terms_json"]),
                article_types=json.loads(row["article_types_json"]),
            )
            candidate_count += int(result.candidate_priority)
            non_original_count += int(result.obvious_non_original_type)
            connection.execute(
                """
                INSERT INTO deterministic_screens(
                    pmid, rules_version, cancer_hit, omics_hit,
                    candidate_priority, cancer_terms_json, omics_terms_json,
                    screened_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(pmid, rules_version) DO UPDATE SET
                    cancer_hit=excluded.cancer_hit,
                    omics_hit=excluded.omics_hit,
                    candidate_priority=excluded.candidate_priority,
                    cancer_terms_json=excluded.cancer_terms_json,
                    omics_terms_json=excluded.omics_terms_json,
                    screened_at=excluded.screened_at
                """,
                (
                    row["pmid"],
                    rules.version,
                    int(bool(result.cancer_terms)),
                    int(bool(result.omics_terms)),
                    int(result.candidate_priority),
                    json_text(result.cancer_terms),
                    json_text(result.omics_terms),
                    screened_at,
                ),
            )
    return {
        "screened": len(rows),
        "candidate_priority": candidate_count,
        "obvious_non_original_type": non_original_count,
        "unmatched_not_excluded": len(rows) - candidate_count,
    }
