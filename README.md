# ArticleBlueprintOS

ArticleBlueprintOS builds a reproducible, journal-first corpus of recent
computationally led cancer-omics research. The first release enumerates the
complete 2023-present PubMed universe for a curated multi-tier journal
whitelist, preserves every
record, and adds high-recall machine screening plus auditable human review
queues. Full text is retrieved only after a paper-level inclusion list has been
reviewed.

## Start here

- [`docs/PROJECT_CHARTER.md`](docs/PROJECT_CHARTER.md) — scope, definition of
  done, data boundaries, and PR lifecycle.
- [`docs/PROJECT_SUMMARY.md`](docs/PROJECT_SUMMARY.md) — current progress and
  open work.
- [`docs/STEP1_MASTER_UNIVERSE_DESIGN.md`](docs/STEP1_MASTER_UNIVERSE_DESIGN.md)
  — locked design for the first historical-backfill step.
- [`docs/STEP2_HISTORICAL_BACKFILL_DESIGN.md`](docs/STEP2_HISTORICAL_BACKFILL_DESIGN.md)
  — locked execution and coverage design for the complete backfill.
- [`Worklog.md`](Worklog.md) — append-only history after PRs are merged.

## Quick start

The code uses only the Python standard library and supports Python 3.11+.

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
article-blueprint init-db --db "$ARTICLE_BLUEPRINT_DATA/metadata.sqlite3"
article-blueprint validate-registry --start 2025-01-01 --end 2025-12-31 \
  --email you@example.org
article-blueprint enumerate --db "$ARTICLE_BLUEPRINT_DATA/metadata.sqlite3" \
  --raw-dir "$ARTICLE_BLUEPRINT_DATA/raw/pubmed" \
  --start 2023-01-01 --end 2026-09-02 --email you@example.org
article-blueprint screen --db "$ARTICLE_BLUEPRINT_DATA/metadata.sqlite3"
article-blueprint status --db "$ARTICLE_BLUEPRINT_DATA/metadata.sqlite3"
```

Set `ARTICLE_BLUEPRINT_DATA` to a directory outside this repository. In the
Stelligen workspace the canonical location is configured through
`BIOWORKSPACE_ROOT`:

```bash
export ARTICLE_BLUEPRINT_DATA="${BIOWORKSPACE_ROOT}/DATA/1.Databases/article_blueprint_os"
```

Do not put the SQLite database, downloaded PDFs, API responses, or exports in
this repository. See the [dataset manifest](datasets/cancer_computational_omics_corpus_v1/dataset.md).

## Journal policy

The v1 registry separates `Gold`, `Silver`, `Methods`, and `Supplementary`
whitelist tiers and maintains an explicit journal/publisher-family blacklist.
Pure review journals are not enumerated. Tiers control retrieval priority, not
automatic paper inclusion. See [`config/journals.json`](config/journals.json)
and [`config/journal_blacklist.json`](config/journal_blacklist.json).

## Screening contract

Deterministic rules only raise candidates; a missing keyword is never an
exclusion. Structured LLM screening and human figure/full-text review are
separate, provenance-bearing decisions. A seeded 10% sample of LLM `NO`
decisions is reserved for false-negative auditing.

## Development

```bash
python3 -m unittest discover -s tests -v
```

Every change is developed on a branch and submitted as a GitHub PR. Nothing is
merged without explicit user approval for that PR.
